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

# ── Clients (initialised outside handler for connection reuse) ────────────
ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# ── Environment variables injected by Terraform ──────────────────────────
AUDIT_BUCKET = os.environ["AUDIT_BUCKET"]
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")


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
