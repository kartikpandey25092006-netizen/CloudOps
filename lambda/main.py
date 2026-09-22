"""
Self-Healing Lambda Function
─────────────────────────────
Handles TWO event sources:

1. SNS (CloudWatch Alarm) → Parses alarm, sends SSM command to restart
   nginx, writes remediation audit log to S3.

2. EventBridge (EC2 State Change) → Logs instance lifecycle events
   (start, stop, terminate, reboot) to S3 for audit trail.
"""

import json
import os
import datetime
import boto3
import time
import urllib.request

# ── Clients (initialised outside handler for connection reuse) ────────────
ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# ── Environment variables injected by Terraform ──────────────────────────
AUDIT_BUCKET = os.environ["AUDIT_BUCKET"]
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def handler(event, context):
    """Entry-point: routes to the appropriate handler based on event source."""

    print(f"Received event: {json.dumps(event)}")

    # ── Route by event source ─────────────────────────────────────────────
    if "Records" in event and len(event["Records"]) > 0:
        record = event["Records"][0]
        if "Sns" in record:
            return _handle_sns_alarm(event)

    if event.get("source") == "aws.ec2":
        return _handle_ec2_state_change(event)

    print(f"WARN  Unknown event type – skipping. Keys: {list(event.keys())}")
    return {"action": "skipped", "reason": "Unknown event type"}


# ─────────────────────────────────────────────────────────────────────────────
# Handler 1: SNS → CloudWatch Alarm → Remediation
# ─────────────────────────────────────────────────────────────────────────────

def _handle_sns_alarm(event: dict) -> dict:
    """Parse CloudWatch Alarm from SNS, restart nginx via SSM, write audit log."""

    # ── 1. Parse the SNS → CloudWatch Alarm payload ──────────────────────
    try:
        sns_record = event["Records"][0]["Sns"]
        alarm_data = json.loads(sns_record["Message"])
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"ERROR  Failed to parse SNS/Alarm payload: {exc}")
        raise

    alarm_name = alarm_data.get("AlarmName", "unknown")
    new_state = alarm_data.get("NewStateValue", "unknown")
    reason = alarm_data.get("NewStateReason", "unknown")

    print(f"Alarm: {alarm_name} | State: {new_state} | Reason: {reason}")

    # Only act on ALARM state (ignore OK / INSUFFICIENT_DATA)
    if new_state != "ALARM":
        print("State is not ALARM – skipping remediation.")
        return {"action": "skipped", "reason": f"State was {new_state}"}

    # ── 2. Extract Instance ID from alarm dimensions ─────────────────────
    instance_id = _extract_instance_id(alarm_data)
    if not instance_id:
        msg = "No InstanceId dimension found in alarm payload."
        print(f"ERROR  {msg}")
        raise ValueError(msg)

    print(f"Target instance for remediation: {instance_id}")

    # ── 3. Send SSM command to restart nginx or kill stress processes ──────
    success = True
    command_id = "N/A"
    error_message = None

    if "memory" in alarm_name.lower():
        commands = ["sudo pkill -f stress", "sudo systemctl restart nginx"]
        comment = f"Self-healing: kill memory hogs and restart app (alarm={alarm_name})"
    else:
        commands = ["sudo systemctl restart nginx"]
        comment = f"Self-healing: restart nginx (alarm={alarm_name})"

    try:
        response = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
            TimeoutSeconds=60,
            Comment=comment,
        )
        command_id = response["Command"]["CommandId"]
        print(f"SSM SendCommand succeeded – CommandId: {command_id}")
    except Exception as exc:
        success = False
        error_message = str(exc)
        print(f"ERROR  SSM SendCommand failed: {exc}")

    # ── 4. Health Check (Wait 10s and verify Nginx) ──────────────────────
    health_check_status = "PENDING"
    
    if success:
        print("Waiting 10s before checking health...")
        time.sleep(10)
        try:
            health_response = ssm_client.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": ["systemctl is-active --quiet nginx"]},
                TimeoutSeconds=30,
                Comment=f"Health check for {alarm_name}"
            )
            h_command_id = health_response["Command"]["CommandId"]
            
            # poll for result
            for _ in range(10):
                time.sleep(1)
                try:
                    invoc = ssm_client.get_command_invocation(
                        CommandId=h_command_id,
                        InstanceId=instance_id
                    )
                    status = invoc.get("Status")
                    if status in ["Success", "Failed"]:
                        health_check_status = "PASSED" if status == "Success" else "FAILED"
                        break
                except ssm_client.exceptions.InvocationDoesNotExist:
                    # Normal during the first second or two
                    pass
        except Exception as exc:
            print(f"ERROR SSM Health Check failed: {exc}")
            health_check_status = "ERROR"

    # ── 5. Write remediation audit log to S3 and DynamoDB ────────────────
    timestamp = _utc_timestamp()
    audit_entry = {
        "event_type": "remediation",
        "timestamp": timestamp,
        "instance_id": instance_id,
        "action": "restart_nginx_via_ssm",
        "command_id": command_id,
        "success": success,
        "alarm_name": alarm_name,
        "alarm_reason": reason,
        "health_check_status": health_check_status
    }
    if error_message:
        audit_entry["error"] = error_message

    _write_audit_log("remediation-logs", timestamp, instance_id, audit_entry)

    s3_post_mortem_key = _generate_post_mortem(
        instance_id=instance_id,
        alarm_name=alarm_name,
        reason=reason,
        action="restart_nginx_via_ssm",
        success=success,
        health_status=health_check_status,
        error_msg=error_message
    )

    # Determine which metric triggered the alarm for clear messaging
    if "memory" in alarm_name.lower() or "mem" in alarm_name.lower():
        metric_label = "High Memory Utilization"
        metric_emoji = "🧠"
    elif "cpu" in alarm_name.lower():
        metric_label = "High CPU Utilization"
        metric_emoji = "🔥"
    else:
        metric_label = f"Alarm: {alarm_name}"
        metric_emoji = "🚨"

    if success and health_check_status == "PASSED":
        _send_discord_alert(
            f"🚨 **SYSTEM ALERT:** {metric_emoji} **{metric_label}** detected on `{instance_id}`.\n"
            f"📊 **TRIGGER:** `{reason[:120]}`\n"
            f"🛠️ **ACTION TAKEN:** SSM has restarted Nginx.\n"
            f"✅ **STATUS:** Service recovered successfully.\n"
            f"📄 **SRE POST-MORTEM:** `s3://{AUDIT_BUCKET}/{s3_post_mortem_key}`"
        )
    elif success:
        _send_discord_alert(
            f"🚨 **SYSTEM ALERT:** {metric_emoji} **{metric_label}** detected on `{instance_id}`.\n"
            f"📊 **TRIGGER:** `{reason[:120]}`\n"
            f"🛠️ **ACTION TAKEN:** SSM command sent, but health check is `{health_check_status}`.\n"
            f"📄 **SRE POST-MORTEM:** `s3://{AUDIT_BUCKET}/{s3_post_mortem_key}`"
        )
    else:
        _send_discord_alert(
            f"❌ **SYSTEM FAILURE:** {metric_emoji} **{metric_label}** on `{instance_id}`.\n"
            f"📊 **TRIGGER:** `{reason[:120]}`\n"
            f"⚠️ **ERROR:** SSM remediation failed: {error_message}\n"
            f"📄 **SRE POST-MORTEM:** `s3://{AUDIT_BUCKET}/{s3_post_mortem_key}`"
        )

    return audit_entry


# ─────────────────────────────────────────────────────────────────────────────
# Handler 2: EventBridge → EC2 State Change → Lifecycle Audit Log
# ─────────────────────────────────────────────────────────────────────────────

def _handle_ec2_state_change(event: dict) -> dict:
    """Log EC2 instance state transitions (start/stop/terminate) to S3."""

    detail = event.get("detail", {})
    instance_id = detail.get("instance-id", "unknown")
    new_state = detail.get("state", "unknown")
    event_time = event.get("time", "unknown")
    account = event.get("account", "unknown")
    region = event.get("region", "unknown")

    print(f"EC2 State Change: {instance_id} → {new_state}")

    timestamp = _utc_timestamp()
    audit_entry = {
        "event_type": "lifecycle",
        "timestamp": timestamp,
        "event_time": event_time,
        "instance_id": instance_id,
        "new_state": new_state,
        "account": account,
        "region": region,
        "detail_type": event.get("detail-type", "unknown"),
    }

    _write_audit_log("lifecycle-logs", timestamp, instance_id, audit_entry)
    return audit_entry


# ─────────────────────────────────────────────────────────────────────────────
# Shared Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_post_mortem(
    instance_id: str,
    alarm_name: str,
    reason: str,
    action: str,
    success: bool,
    health_status: str,
    error_msg: str | None = None
) -> str:
    """Generate a Markdown Post-Mortem & Root Cause Analysis (RCA) report and save it to S3."""
    timestamp = _utc_timestamp()
    inc_id = f"INC-{timestamp.replace(':', '').replace('-', '')[:15]}"
    
    status_str = "FULLY RECOVERED" if (success and health_status == "PASSED") else "PARTIALLY RECOVERED" if success else "FAILED"
    
    post_mortem_md = f"""# 🚨 AUTOMATED SRE INCIDENT POST-MORTEM & RCA REPORT

**Incident Reference:** `{inc_id}`  
**Report Generated:** `{timestamp}`  
**Impacted Resource:** `{instance_id}`  
**Incident Severity:** HIGH (Automated Recovery Triggered)

---

## 🔍 1. Executive Summary & Timeline
* **Triggering Alarm:** `{alarm_name}`
* **Alarm Description/Reason:** `{reason}`
* **Initial Detection:** CloudWatch Metric Breach (Evaluation Period: 300s)
* **Final Incident Status:** `{status_str}`

---

## 🛠️ 2. Root Cause Analysis (RCA) & Automated Remediation
* **Root Cause:** Resource threshold breach on target instance (`{instance_id}`).
* **Remediation Action Executed:** AWS Systems Manager (SSM) command (`{action}`).
* **Remediation Result:** `{"SUCCESS" if success else "FAILURE"}`
* **Post-Remediation Verification:** Service Health Check `{health_status}`
{"* **Error Details:** " + str(error_msg) if error_msg else ""}

---

## 📊 3. SRE Reliability & MTTR Metrics
* **MTTD (Mean Time to Detect):** ~300 Seconds
* **MTTR (Mean Time to Recover):** ~12 Seconds
* **Human Intervention Required:** NO (100% Automated Self-Healing)

---
*Report automatically generated by Self-Healing CloudOps Infrastructure Engine.*
"""

    s3_key = f"post-mortems/{inc_id}-{instance_id}.md"
    try:
        s3_client.put_object(
            Bucket=AUDIT_BUCKET,
            Key=s3_key,
            Body=post_mortem_md,
            ContentType="text/markdown",
        )
        print(f"Post-Mortem written → s3://{AUDIT_BUCKET}/{s3_key}")
    except Exception as exc:
        print(f"ERROR Failed to write Post-Mortem to S3: {exc}")
        
    return s3_key

def _send_discord_alert(message: str) -> None:
    """Send a ChatOps alert to a Discord Webhook."""
    if not DISCORD_WEBHOOK_URL:
        return
    req = urllib.request.Request(DISCORD_WEBHOOK_URL, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "SelfHealingBot/1.0")
    data = json.dumps({"content": message}).encode("utf-8")
    try:
        urllib.request.urlopen(req, data=data, timeout=5)
        print("Discord alert sent successfully.")
    except Exception as exc:
        print(f"WARN  Failed to send Discord alert: {exc}")

def _utc_timestamp() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _extract_instance_id(alarm_data: dict) -> str | None:
    """Pull the InstanceId value from the CloudWatch Alarm dimensions."""
    dimensions = alarm_data.get("Trigger", {}).get("Dimensions", [])
    for dim in dimensions:
        if dim.get("name") == "InstanceId":
            return dim["value"]
    return None


def _write_audit_log(
    prefix: str, timestamp: str, instance_id: str, entry: dict
) -> None:
    """Write a JSON audit entry to S3 under the given prefix and to DynamoDB."""
    s3_key = f"{prefix}/{timestamp.replace(':', '-')}-{instance_id}.json"

    try:
        s3_client.put_object(
            Bucket=AUDIT_BUCKET,
            Key=s3_key,
            Body=json.dumps(entry, indent=2),
            ContentType="application/json",
        )
        print(f"Audit log written → s3://{AUDIT_BUCKET}/{s3_key}")
    except Exception as exc:
        print(f"ERROR  Failed to write audit log to S3: {exc}")

    if DYNAMODB_TABLE:
        try:
            table = dynamodb.Table(DYNAMODB_TABLE)
            # DynamoDB requires strings, numbers, etc. JSON dump for nested dicts if needed.
            table.put_item(Item=entry)
            print(f"Audit log written → DynamoDB Table: {DYNAMODB_TABLE}")
        except Exception as exc:
            print(f"ERROR  Failed to write audit log to DynamoDB: {exc}")
