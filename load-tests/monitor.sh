#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Real-Time Monitor — Terminal Dashboard
# ═══════════════════════════════════════════════════════════════
#
# Polls CloudWatch every 30 seconds and displays:
#   - Current CPU utilization
#   - Alarm states (all 4 alarms)
#   - Instance status
#   - Latest Lambda invocations
#
# Usage:  ./monitor.sh
# Stop:   Ctrl+C
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

INSTANCE_ID=$(cd "$TERRAFORM_DIR" && terraform output -raw ec2_instance_id)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

colorize_state() {
  case "$1" in
    OK) echo -e "${GREEN}$1${NC}" ;;
    ALARM) echo -e "${RED}$1${NC}" ;;
    INSUFFICIENT_DATA) echo -e "${YELLOW}$1${NC}" ;;
    *) echo "$1" ;;
  esac
}

echo -e "${BOLD}CloudOps Real-Time Monitor${NC}"
echo -e "Instance: ${CYAN}${INSTANCE_ID}${NC}"
echo -e "Press Ctrl+C to stop"
echo ""

while true; do
  TIMESTAMP=$(date '+%H:%M:%S')
  
  # Get CPU
  CPU=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/EC2 \
    --metric-name CPUUtilization \
    --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
    --start-time "$(date -u -v-5M '+%Y-%m-%dT%H:%M:%S')" \
    --end-time "$(date -u '+%Y-%m-%dT%H:%M:%S')" \
    --period 60 \
    --statistics Average \
    --query 'Datapoints | sort_by(@, &Timestamp) | [-1].Average' \
    --output text 2>/dev/null || echo "N/A")
  
  # Get all alarm states
  ALARMS=$(aws cloudwatch describe-alarms \
    --alarm-name-prefix "self-healing" \
    --query 'MetricAlarms[].{Name:AlarmName,State:StateValue}' \
    --output text 2>/dev/null)
  
  # Display
  echo -e "─────────────────────────────────────────────── ${CYAN}${TIMESTAMP}${NC}"
  
  # CPU bar
  CPU_INT=${CPU%.*}
  if [ "$CPU_INT" -gt 75 ] 2>/dev/null; then
    echo -e "  CPU:  ${RED}${CPU}%${NC} ████████████████████ ${RED}ABOVE THRESHOLD${NC}"
  elif [ "$CPU_INT" -gt 50 ] 2>/dev/null; then
    echo -e "  CPU:  ${YELLOW}${CPU}%${NC} ██████████████░░░░░░"
  elif [ "$CPU_INT" -gt 0 ] 2>/dev/null; then
    echo -e "  CPU:  ${GREEN}${CPU}%${NC} ██████░░░░░░░░░░░░░░"
  else
    echo -e "  CPU:  ${YELLOW}${CPU}${NC}"
  fi
  
  # Alarms
  echo -e "  Alarms:"
  while IFS=$'\t' read -r name state; do
    if [ -n "$name" ]; then
      SHORT_NAME=$(echo "$name" | sed 's/self-healing-//')
      echo -e "    $(colorize_state "$state")  $SHORT_NAME"
    fi
  done <<< "$ALARMS"
  
  echo ""
  sleep 30
done
