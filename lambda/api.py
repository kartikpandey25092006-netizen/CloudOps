import os
import json
import boto3
import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# ── Clients (initialised outside handler for connection reuse) ────────────
cloudwatch = boto3.client("cloudwatch")
ec2 = boto3.client("ec2")
dynamodb = boto3.resource("dynamodb")

INSTANCE_ID = os.environ.get("INSTANCE_ID")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")
STATE_TABLE = os.environ.get("STATE_TABLE")

def handler(event, context):
    raw_path = event.get('rawPath', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    print(f"Received API request: {method} {raw_path}")
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        }
    
    try:
        if raw_path == "/api/maintenance" and method == "POST":
            body = json.loads(event.get("body", "{}"))
            maintenance_mode = body.get("maintenance", False)
            
            alarms = cloudwatch.describe_alarms(AlarmNamePrefix="self-healing")["MetricAlarms"]
            alarm_names = [a["AlarmName"] for a in alarms]
            
            if alarm_names:
                if maintenance_mode:
                    cloudwatch.disable_alarm_actions(AlarmNames=alarm_names)
                else:
                    cloudwatch.enable_alarm_actions(AlarmNames=alarm_names)
                
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"},
                "body": json.dumps({"success": True, "maintenance": maintenance_mode, "alarms_updated": len(alarm_names)})
            }
            
        else: # GET /api/status
            time_range = event.get("queryStringParameters", {}).get("time_range", "40m") if event.get("queryStringParameters") else "40m"
            
            uptime_seconds = get_uptime(INSTANCE_ID)
            cpu_history, current_cpu, is_simulating = get_cpu_metrics(INSTANCE_ID, time_range)
            memory_history, current_memory, is_memory_simulating = get_memory_metrics(INSTANCE_ID, time_range)
            audit_logs = get_audit_logs(INSTANCE_ID)
            healing_state = get_healing_state()
            
            alarms = cloudwatch.describe_alarms(AlarmNamePrefix="self-healing")["MetricAlarms"]
            maintenance_mode = any(a.get("ActionsEnabled") == False for a in alarms)
            
            body = {
                "uptime": uptime_seconds,
                "cpu_history": cpu_history,
                "current_cpu": current_cpu,
                "is_simulating": is_simulating,
                "memory_history": memory_history,
                "current_memory": current_memory,
                "is_memory_simulating": is_memory_simulating,
                "audit_logs": audit_logs,
                "maintenance_mode": maintenance_mode,
                "healing_state": healing_state
            }
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps(body, cls=DecimalEncoder)
            }
            
    except Exception as e:
        print(f"API Error: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }

def get_uptime(instance_id):
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        launch_time = instance["LaunchTime"]
        now = datetime.datetime.now(datetime.timezone.utc)
        uptime = (now - launch_time).total_seconds()
        return int(uptime)
    except Exception as e:
        print(f"Error fetching uptime: {e}")
        return 0

def get_cpu_metrics(instance_id, time_range="40m"):
    try:
        end_time = datetime.datetime.now(datetime.timezone.utc)
        
        if time_range == "24h":
            start_time = end_time - datetime.timedelta(hours=24)
            period = 3600
            num_points = 24
        elif time_range == "1h":
            start_time = end_time - datetime.timedelta(hours=1)
            period = 180
            num_points = 20
        else: # default 40m
            start_time = end_time - datetime.timedelta(minutes=40)
            period = 120
            num_points = 20
        
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=["Average"]
        )
        
        datapoints = response.get("Datapoints", [])
        # Sort by timestamp ascending
        datapoints.sort(key=lambda x: x["Timestamp"])
        
        # Format for frontend
        history = []
        for dp in datapoints:
            history.append({
                "time": dp["Timestamp"].isoformat(),
                "cpu": round(dp["Average"], 1)
            })
            
        # Ensure we always have enough points for the graph by padding with 0s if needed
        while len(history) < num_points:
            history.insert(0, {"time": "", "cpu": 0})
            
        # Take exactly the last num_points
        history = history[-num_points:]
        
        current_cpu = history[-1]["cpu"] if history else 0
        is_simulating = current_cpu > 75.0
        
        return history, current_cpu, is_simulating
    except Exception as e:
        print(f"Error fetching CPU: {e}")
        num_points = 24 if time_range == "24h" else 20
        history = [{"time": "", "cpu": 0} for _ in range(num_points)]
        return history, 0, False

def get_memory_metrics(instance_id, time_range="40m"):
    try:
        end_time = datetime.datetime.now(datetime.timezone.utc)
        
        if time_range == "24h":
            start_time = end_time - datetime.timedelta(hours=24)
            period = 3600
            num_points = 24
        elif time_range == "1h":
            start_time = end_time - datetime.timedelta(hours=1)
            period = 180
            num_points = 20
        else: # default 40m
            start_time = end_time - datetime.timedelta(minutes=40)
            period = 120
            num_points = 20
        
        response = cloudwatch.get_metric_statistics(
            Namespace="CWAgent",
            MetricName="mem_used_percent",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=["Average"]
        )
        
        datapoints = response.get("Datapoints", [])
        # Sort by timestamp ascending
        datapoints.sort(key=lambda x: x["Timestamp"])
        
        # Format for frontend
        history = []
        for dp in datapoints:
            history.append({
                "time": dp["Timestamp"].isoformat(),
                "memory": round(dp["Average"], 1)
            })
            
        # Ensure we always have enough points for the graph by padding with 0s if needed
        while len(history) < num_points:
            history.insert(0, {"time": "", "memory": 0})
            
        # Take exactly the last num_points
        history = history[-num_points:]
        
        current_memory = history[-1]["memory"] if history else 0
        is_memory_simulating = current_memory > 85.0
        
        return history, current_memory, is_memory_simulating
    except Exception as e:
        print(f"Error fetching Memory: {e}")
        num_points = 24 if time_range == "24h" else 20
        history = [{"time": "", "memory": 0} for _ in range(num_points)]
        return history, 0, False

def get_audit_logs(instance_id, limit=50):
    table = dynamodb.Table(DYNAMODB_TABLE)
    now = datetime.datetime.now(datetime.timezone.utc)
    twenty_four_hours_ago = (now - datetime.timedelta(hours=24)).isoformat()
    
    try:
        response = table.query(
            KeyConditionExpression=Key("instance_id").eq(instance_id) & Key("timestamp").gte(twenty_four_hours_ago),
            ScanIndexForward=False, # descending order
            Limit=limit
        )
        return response.get("Items", [])
    except Exception as e:
        print(f"DynamoDB query failed: {e}")
        return []

def get_healing_state():
    if not STATE_TABLE:
        return {}
    
    table = dynamodb.Table(STATE_TABLE)
    try:
        # Fetch both ec2-health and app-health
        states = {}
        for rid in ["ec2-health", "app-health"]:
            resp = table.get_item(Key={"resource_id": rid})
            if "Item" in resp:
                states[rid] = resp["Item"]
            else:
                states[rid] = {"status": "UNKNOWN", "attempts": 0}
        return states
    except Exception as e:
        print(f"Error fetching state: {e}")
        return {}

# Custom JSON encoder to handle DynamoDB Decimals
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 > 0:
                return float(obj)
            else:
                return int(obj)
        return super(DecimalEncoder, self).default(obj)
