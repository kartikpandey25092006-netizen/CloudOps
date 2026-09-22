# Self-Healing Cloud Infrastructure on AWS

A fully automated self-healing system with multi-layered recovery, operational alerting, lifecycle auditing, and a real-time CloudWatch dashboard — all within AWS Free Tier.

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │          SELF-HEALING LOOPS             │
                         └─────────────────────────────────────────┘

  LOOP 1: Service Recovery (High CPU → Restart nginx)
  ───────────────────────────────────────────────────
  ┌──────────────┐   CPUUtilization > 75%    ┌─────────────────┐
  │  EC2 Instance │──── CloudWatch Alarm ────▶│   SNS Topic     │──── Email Alert
  │  (t2.micro)  │                           └────────┬────────┘
  │  nginx + SSM │                                    │
  └──────▲───────┘                                    ▼
         │                                   ┌─────────────────┐
         │  SSM: systemctl restart nginx     │  Lambda Function │
         └───────────────────────────────────│  (Python 3.12)  │
                                             └────────┬────────┘
                                                      │
                                             ┌────────▼────────┐
                                             │   S3 Bucket     │
                                             │  (Audit Logs)   │
                                             │  + Versioning   │
                                             └─────────────────┘

  LOOP 2: Hardware Recovery (System Status Check → Auto Recovery)
  ──────────────────────────────────────────────────────────────
  ┌──────────────┐  StatusCheckFailed_System  ┌─────────────────┐
  │  EC2 Instance │──── CloudWatch Alarm ─────▶│  EC2 Auto       │
  │  (t2.micro)  │                            │  Recover Action  │
  └──────▲───────┘                            └────────┬────────┘
         └─────────────────────────────────────────────┘
         (Preserves: Instance ID, IPs, EBS volumes)

  LOOP 3: OS Recovery (Instance Status Check → Auto Reboot)
  ────────────────────────────────────────────────────────
  ┌──────────────┐  StatusCheckFailed_Instance ┌────────────────┐
  │  EC2 Instance │──── CloudWatch Alarm ──────▶│  EC2 Auto      │
  │  (t2.micro)  │                             │  Reboot Action  │
  └──────▲───────┘                             └───────┬────────┘
         └─────────────────────────────────────────────┘

  OBSERVABILITY: EventBridge → Lambda → S3 Lifecycle Logs
  ──────────────────────────────────────────────────────
  ┌──────────────┐  State Change Event   ┌──────────────┐   ┌────────────┐
  │  EC2 Instance │─── EventBridge ──────▶│    Lambda    │──▶│  S3 Bucket │
  └──────────────┘  (start/stop/reboot)  └──────────────┘   └────────────┘

  FRONTEND: React Dashboard via S3 & SSM
  ──────────────────────────────────────────────────────
  ┌──────────────┐    S3 Sync   ┌────────────────┐   
  │  S3 Bucket   │◀─────────────│  EC2 Instance  │   
  │ (React Build)│              │  Nginx Server  │   
  └──────────────┘              └────────────────┘   
```

## Features Summary

| # | Feature | Description |
|---|---------|-------------|
| 1 | **CPU Self-Healing** | CloudWatch alarm → SNS → Lambda → SSM restart nginx |
| 2 | **EC2 Auto Recovery** | Hardware failure → automatic instance migration |
| 3 | **Instance Health Check** | OS-level failure → automatic reboot |
| 4 | **SNS Email Alerts** | Email notifications on alarms and remediation |
| 5 | **Lambda Error Alarm** | Detects if the self-healing mechanism itself fails |
| 6 | **CloudWatch Dashboard** | Single-pane-of-glass for CPU, health, Lambda metrics, alarm states |
| 7 | **S3 Bucket Versioning** | Protects audit logs from accidental overwrites |
| 8 | **EventBridge Lifecycle Logging** | Captures all EC2 state changes to S3 audit trail |
| 9 | **IAM Least Privilege** | Every role is scoped to specific resources |

## Prerequisites

1. **AWS Account** with Free Tier eligibility
2. **AWS CLI v2** installed (`brew install awscli` on Mac) and configured (`aws configure`)
3. **Terraform >= 1.5** installed (`brew install terraform` on Mac)
4. **Default VPC** must exist in the target region

```bash
aws --version                   # Verify AWS CLI installation
aws sts get-caller-identity     # Verify credentials
terraform --version              # Verify Terraform >= 1.5
```

## Project Structure

```
AWS/
├── lambda/
│   └── main.py              # Lambda: remediation + lifecycle logger
├── terraform/
│   ├── main.tf              # Provider, data sources
│   ├── variables.tf         # Configurable inputs
│   ├── s3.tf                # Audit bucket + versioning
│   ├── iam.tf               # EC2 + Lambda IAM roles
│   ├── ec2.tf               # Security group + EC2 instance
│   ├── monitoring.tf        # 4 CloudWatch alarms + 2 SNS topics
│   ├── lambda.tf            # Lambda function + SNS subscription
│   ├── dashboard.tf         # CloudWatch dashboard
│   ├── eventbridge.tf       # EC2 state change rule
│   └── outputs.tf           # All resource IDs & test commands
├── docs/                    # Project Context & Architecture Docs
├── RULES.md                 # AI Development Rules
├── TASKS.md                 # Prioritized Backlog
└── README.md
```

## Project Documentation
For an in-depth understanding of the architecture, design, security, and future plans, refer to the `docs/` directory:
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- [PRD.md](./docs/PRD.md)
- [SECURITY.md](./docs/SECURITY.md)
- [TEST_PLAN.md](./docs/TEST_PLAN.md)
- [DECISIONS.md](./docs/DECISIONS.md)
- [MEMORY.md](./docs/MEMORY.md)

---

## Step-by-Step Deployment

### Step 1: Initialise Terraform

```bash
cd AWS/terraform
terraform init
```

### Step 2: Preview the Plan

```bash
# Without email alerts
terraform plan

# With email alerts
terraform plan -var="alert_email=your-email@example.com"
```

### Step 3: Deploy the Stack

```bash
# Without email alerts
terraform apply

# With email alerts (recommended)
terraform apply -var="alert_email=your-email@example.com"
```

Type `yes` when prompted. Deployment takes ~2–3 minutes.

> **📧 Important:** If you provided an email, check your inbox for **two** SNS subscription confirmation emails (one for remediation alerts, one for ops alerts). **You must click "Confirm subscription"** in both emails to receive notifications.

### Step 4: Verify the Deployment

Wait **~3 minutes** for UserData to finish installing nginx.

```bash
# 1. Check nginx is running
curl http://$(terraform output -raw ec2_public_ip)

# 2. Verify SSM registration
aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=$(terraform output -raw ec2_instance_id)" \
  --query "InstanceInformationList[0].PingStatus"
# Expected: "Online"

# 3. Check all 4 alarms exist
aws cloudwatch describe-alarms \
  --alarm-name-prefix "self-healing" \
  --query "MetricAlarms[].{Name:AlarmName, State:StateValue}" \
  --output table
```

### Step 5: Deploy the React Frontend

The infrastructure is ready. Now build and deploy the React CloudOps Dashboard to the EC2 instance using the automated script:

```bash
cd AWS
./deploy-frontend.sh
```

Wait for the script to say `Deployment successful!`. Then:

```bash
# Open the dashboard in your browser
echo "http://$(cd terraform && terraform output -raw ec2_public_ip)"
```

### Step 6: Explore the CloudWatch Dashboard

```bash
echo "Dashboard: $(cd terraform && terraform output -raw dashboard_url)"
```

---

## Testing the Self-Healing Loop

### Method 1: CPU Spike via SSM (Full End-to-End Test)

```bash
# Trigger 95% CPU for 10 minutes
aws ssm send-command \
  --instance-ids "$(terraform output -raw ec2_instance_id)" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["stress-ng --cpu 1 --cpu-load 95 --timeout 600s &"]' \
  --comment "Test: trigger CPU spike"
```

The alarm takes **5–10 minutes** to fire (300s evaluation period with basic monitoring).

```bash
# Monitor alarm state
watch -n 60 'aws cloudwatch describe-alarms \
  --alarm-names "self-healing-high-cpu" \
  --query "MetricAlarms[0].StateValue" \
  --output text'
```

### Method 2: Direct Lambda Invocation (Instant Test)

```bash
INSTANCE_ID=$(terraform output -raw ec2_instance_id)

aws lambda invoke \
  --function-name "self-healing-remediation" \
  --cli-binary-format raw-in-base64-out \
  --payload "{
    \"Records\": [{
      \"Sns\": {
        \"Message\": \"{\\\"AlarmName\\\":\\\"self-healing-high-cpu\\\",\\\"NewStateValue\\\":\\\"ALARM\\\",\\\"NewStateReason\\\":\\\"Manual test\\\",\\\"Trigger\\\":{\\\"Dimensions\\\":[{\\\"name\\\":\\\"InstanceId\\\",\\\"value\\\":\\\"${INSTANCE_ID}\\\"}]}}\"
      }
    }]
  }" \
  /dev/stdout
```

### Verifying Results

```bash
# 1. Check Lambda logs
aws logs tail "/aws/lambda/self-healing-remediation" --since 30m

# 2. List remediation audit logs
aws s3 ls "s3://$(terraform output -raw s3_audit_bucket)/remediation-logs/"

# 3. List lifecycle audit logs
aws s3 ls "s3://$(terraform output -raw s3_audit_bucket)/lifecycle-logs/"

# 4. Read the latest remediation log
LATEST=$(aws s3 ls "s3://$(terraform output -raw s3_audit_bucket)/remediation-logs/" \
  --recursive | sort | tail -1 | awk '{print $4}')
aws s3 cp "s3://$(terraform output -raw s3_audit_bucket)/$LATEST" -
```

### Stopping the Stress Test

```bash
aws ssm send-command \
  --instance-ids "$(terraform output -raw ec2_instance_id)" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["pkill -f stress-ng"]' \
  --comment "Stop stress test"
```

---

## Free Tier Compliance

| Resource              | Free Tier Limit              | This Stack Uses              |
|-----------------------|------------------------------|------------------------------|
| EC2 (t2.micro)        | 750 hours/month              | 1 instance                   |
| EBS (gp3)             | 30 GB/month                  | 8 GB                         |
| S3 Storage            | 5 GB                         | ~500 KB (Logs + React app)   |
| S3 Requests           | 2,000 PUT / 20,000 GET       | Minimal                      |
| Lambda                | 1M requests + 400K GB-s      | < 100 invocations            |
| CloudWatch Alarms     | 10 standard alarms           | 4 alarms                     |
| CloudWatch Dashboard  | 3 dashboards                 | 1 dashboard                  |
| CloudWatch Logs       | 5 GB ingestion               | < 1 MB                       |
| SNS                   | 1M publishes                 | < 100                        |
| SNS Email             | Unlimited                    | Minimal                      |
| SSM (RunCommand)      | Free                         | Minimal                      |
| EventBridge           | Free (default bus)           | Minimal                      |

> **⚠️ Important:** The Free Tier for EC2 is 750 hours/month. Running 1 instance for a full month uses ~720 hours — well within the limit. Do **not** launch additional instances.

---

## Cleanup

```bash
cd AWS/terraform
terraform destroy
```

Type `yes` when prompted. All resources including the S3 bucket (via `force_destroy = true`) will be removed.

---

## Customisation

```bash
# Use a different region
terraform apply -var="aws_region=eu-west-1"

# Lower the CPU threshold
terraform apply -var="cpu_threshold=50"

# Use t3.micro instead
terraform apply -var="instance_type=t3.micro"

# Add email alerts
terraform apply -var="alert_email=ops-team@example.com"
```
