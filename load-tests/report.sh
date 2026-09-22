#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Post-Test Report Generator
# ═══════════════════════════════════════════════════════════════
#
# Collects all data from CloudWatch, S3, DynamoDB, and Lambda logs
# to produce a comprehensive post-test report.
#
# Usage:  ./report.sh
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

INSTANCE_ID=$(cd "$TERRAFORM_DIR" && terraform output -raw ec2_instance_id)
AUDIT_BUCKET=$(cd "$TERRAFORM_DIR" && terraform output -raw s3_audit_bucket)

# Colors
BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  CloudOps Post-Test Report${NC}"
echo -e "${BOLD}  Generated: $(date)${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ── 1. Instance Info ──────────────────────────────────────────
echo -e "${CYAN}── Instance Info ──${NC}"
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].{ID:InstanceId,Type:InstanceType,State:State.Name,IP:PublicIpAddress,LaunchTime:LaunchTime}' \
  --output table
echo ""

# ── 2. Current Alarm States ──────────────────────────────────
echo -e "${CYAN}── CloudWatch Alarm States ──${NC}"
aws cloudwatch describe-alarms \
  --alarm-name-prefix "self-healing" \
  --query 'MetricAlarms[].{Alarm:AlarmName,State:StateValue,Reason:StateReason}' \
  --output table
echo ""

# ── 3. CPU History (last 30 minutes) ─────────────────────────
echo -e "${CYAN}── CPU History (last 30 min) ──${NC}"
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
  --start-time "$(date -u -v-30M '+%Y-%m-%dT%H:%M:%S')" \
  --end-time "$(date -u '+%Y-%m-%dT%H:%M:%S')" \
  --period 300 \
  --statistics Average Maximum \
  --query 'Datapoints | sort_by(@, &Timestamp)' \
  --output table
echo ""

# ── 4. Recent Lambda Logs ────────────────────────────────────
echo -e "${CYAN}── Lambda Remediation Logs (last 1h) ──${NC}"
aws logs tail "/aws/lambda/self-healing-remediation" --since 1h --format short 2>/dev/null | tail -20 || echo "  (No recent logs)"
echo ""

echo -e "${CYAN}── Lambda Health Manager Logs (last 1h) ──${NC}"
aws logs tail "/aws/lambda/self-healing-health-manager" --since 1h --format short 2>/dev/null | tail -20 || echo "  (No recent logs)"
echo ""

# ── 5. S3 Audit Trail ────────────────────────────────────────
echo -e "${CYAN}── S3 Remediation Audit Logs ──${NC}"
aws s3 ls "s3://${AUDIT_BUCKET}/remediation-logs/" --recursive 2>/dev/null | sort | tail -5 || echo "  (No remediation logs)"
echo ""

echo -e "${CYAN}── S3 Lifecycle Audit Logs ──${NC}"
aws s3 ls "s3://${AUDIT_BUCKET}/lifecycle-logs/" --recursive 2>/dev/null | sort | tail -5 || echo "  (No lifecycle logs)"
echo ""

# ── 6. Read latest remediation log ───────────────────────────
echo -e "${CYAN}── Latest Remediation Log Content ──${NC}"
LATEST=$(aws s3 ls "s3://${AUDIT_BUCKET}/remediation-logs/" --recursive 2>/dev/null | sort | tail -1 | awk '{print $4}')
if [ -n "$LATEST" ]; then
  aws s3 cp "s3://${AUDIT_BUCKET}/$LATEST" - 2>/dev/null | python3 -m json.tool
else
  echo "  (No remediation logs found)"
fi
echo ""

# ── Summary ──────────────────────────────────────────────────
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Report Complete${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
