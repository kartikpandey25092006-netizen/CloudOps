import json
import os
import datetime
import urllib.request
import boto3

dynamodb = boto3.resource("dynamodb")
ec2_client = boto3.client("ec2")
ssm_client = boto3.client("ssm")
sns_client = boto3.client("sns")

STATE_TABLE = os.environ.get("STATE_TABLE")
AUDIT_TABLE = os.environ.get("AUDIT_TABLE")
OPS_TOPIC_ARN = os.environ.get("OPS_TOPIC_ARN")
INSTANCE_ID = os.environ.get("INSTANCE_ID")
MAX_ATTEMPTS = 3
STABILIZATION_TIME_SECONDS = 60

state_table = dynamodb.Table(STATE_TABLE)
audit_table = dynamodb.Table(AUDIT_TABLE)

def _utc_timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def get_state(resource_id):
    try:
        resp = state_table.get_item(Key={"resource_id": resource_id})
        if "Item" in resp:
            return resp["Item"]
    except Exception as e:
        print(f"Error fetching state: {e}")
    
    return {
        "resource_id": resource_id,
        "status": "HEALTHY",
        "attempts": 0,
        "last_attempt_time": "1970-01-01T00:00:00+00:00",
        "problem": ""
    }

def update_state(state):
    try:
        state_table.put_item(Item=state)
    except Exception as e:
        print(f"Error updating state: {e}")

def log_audit_event(event_type, action, problem, success, attempt, error=None):
    entry = {
        "instance_id": INSTANCE_ID,
        "timestamp": _utc_timestamp(),
        "event_type": event_type,
        "action": action,
        "problem": problem,
        "success": success,
        "attempt": attempt
    }
    if error:
        entry["error"] = error
    try:
        audit_table.put_item(Item=entry)
    except Exception as e:
        print(f"Error logging audit: {e}")

def send_sns(subject, message):
    try:
        sns_client.publish(
            TopicArn=OPS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print(f"Error sending SNS: {e}")

def check_ec2_health():
    try:
        resp = ec2_client.describe_instance_status(InstanceIds=[INSTANCE_ID])
        if not resp["InstanceStatuses"]:
            return False, "Instance not found or stopped"
        status = resp["InstanceStatuses"][0]
        sys_status = status["SystemStatus"]["Status"]
        inst_status = status["InstanceStatus"]["Status"]
        if sys_status != "ok":
            return False, "EC2 System Status Check Failed"
        if inst_status != "ok":
            return False, "EC2 Instance Status Check Failed"
        return True, ""
    except Exception as e:
        print(f"Error checking EC2 health: {e}")
        return False, f"Error checking EC2 health: {str(e)}"

def get_instance_ip():
    try:
        resp = ec2_client.describe_instances(InstanceIds=[INSTANCE_ID])
        return resp["Reservations"][0]["Instances"][0].get("PublicIpAddress")
    except Exception as e:
        print(f"Error fetching instance IP: {e}")
        return None

def check_app_health():
    ip = get_instance_ip()
    if not ip:
        return False, "Could not determine instance IP"
    url = f"http://{ip}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True, ""
            return False, f"App returned status {response.status}"
    except Exception as e:
        print(f"Error checking app health: {e}")
        return False, f"App health check failed: {str(e)}"

def process_resource(resource_id, check_func, recovery_action_func, recovery_name):
    print(f"Processing {resource_id}...")
    is_healthy, problem_desc = check_func()
    state = get_state(resource_id)
    
    current_status = state["status"]
    attempts = int(state.get("attempts", 0))
    last_attempt_time = state.get("last_attempt_time", "1970-01-01T00:00:00+00:00")
    
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        last_dt = datetime.datetime.fromisoformat(last_attempt_time)
    except:
        last_dt = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        
    seconds_since_last = (now - last_dt).total_seconds()

    if is_healthy:
        if current_status in ["RECOVERING", "FAILED", "UNHEALTHY"]:
            # State transition to healthy
            state["status"] = "HEALTHY"
            state["attempts"] = 0
            update_state(state)
            
            # Send Success SNS
            subject = "RESILIENTAI RECOVERY SUCCESS"
            msg = f"RESILIENTAI RECOVERY SUCCESS\n\nInstance: {INSTANCE_ID}\nResource: {resource_id}\nProblem: {state.get('problem', 'Unknown')}\nAction: Automatic Recovery\nAttempts: {attempts}\nFinal Status: HEALTHY"
            send_sns(subject, msg)
            
            log_audit_event(
                event_type="remediation",
                action="Verification",
                problem=state.get('problem', 'Unknown'),
                success=True,
                attempt=attempts
            )
            print(f"[{resource_id}] Recovered successfully!")
        return

    # If we reach here, it is UNHEALTHY
    if current_status == "FAILED":
        print(f"[{resource_id}] Still FAILED. Waiting for admin intervention.")
        return
        
    if current_status == "RECOVERING" and seconds_since_last < STABILIZATION_TIME_SECONDS:
        print(f"[{resource_id}] Still waiting for stabilization ({seconds_since_last}s elapsed)")
        return

    # Needs recovery action
    if attempts >= MAX_ATTEMPTS:
        # Reached max attempts
        state["status"] = "FAILED"
        update_state(state)
        
        subject = "RESILIENTAI CRITICAL ALERT"
        msg = f"RESILIENTAI CRITICAL ALERT\n\nInstance: {INSTANCE_ID}\nResource: {resource_id}\nProblem: {problem_desc}\nRecovery Attempts: {attempts}\nFinal Status: FAILED\nAdministrator Intervention Required"
        send_sns(subject, msg)
        
        log_audit_event("remediation", recovery_name, problem_desc, False, attempts)
        print(f"[{resource_id}] Max attempts reached. Marked as FAILED.")
        return

    # Trigger recovery
    attempts += 1
    state["status"] = "RECOVERING"
    state["attempts"] = attempts
    state["last_attempt_time"] = _utc_timestamp()
    state["problem"] = problem_desc
    update_state(state)
    
    subject = "RESILIENTAI ALERT"
    msg = f"RESILIENTAI ALERT\n\nInstance: {INSTANCE_ID}\nResource: {resource_id}\nProblem: {problem_desc}\nAction: Automatic Recovery Initiated\nAttempt: {attempts}\nStatus: RECOVERING"
    send_sns(subject, msg)
    
    try:
        recovery_action_func()
        log_audit_event("remediation", recovery_name, problem_desc, True, attempts)
        print(f"[{resource_id}] Recovery action initiated (Attempt {attempts})")
    except Exception as e:
        log_audit_event("remediation", recovery_name, problem_desc, False, attempts, str(e))
        print(f"[{resource_id}] Recovery action failed: {e}")

def action_reboot_ec2():
    ec2_client.reboot_instances(InstanceIds=[INSTANCE_ID])

def action_restart_nginx():
    ssm_client.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": ["systemctl restart nginx"]},
        TimeoutSeconds=30,
        Comment="Self-Healing App Restart"
    )

def handler(event, context):
    print(f"Running self-healing health manager... (Max attempts: {MAX_ATTEMPTS})")
    
    # 1. Process EC2 Health
    process_resource(
        resource_id="ec2-health",
        check_func=check_ec2_health,
        recovery_action_func=action_reboot_ec2,
        recovery_name="EC2 Reboot"
    )
    
    # 2. Process App Health
    process_resource(
        resource_id="app-health",
        check_func=check_app_health,
        recovery_action_func=action_restart_nginx,
        recovery_name="Service Restart"
    )
    
    print("Health manager complete.")
    return {"statusCode": 200, "body": "OK"}
