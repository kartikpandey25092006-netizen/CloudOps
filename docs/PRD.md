# Product Requirements Document (PRD)

## Product Purpose
The Self-Healing Cloud Architecture is an automated, event-driven infrastructure project designed to detect, log, and recover from failures automatically. It demonstrates modern Site Reliability Engineering (SRE) practices within the AWS Free Tier.

## Problem Being Solved
Manual intervention for basic infrastructure failures (like high CPU or stopped services) leads to prolonged downtime. This system solves that by instantly detecting issues and automatically running remediation scripts.

## Target Users
- Operations Teams (Ops/SRE) who need a single-pane-of-glass dashboard.
- Developers learning self-healing infrastructure patterns.

## Core Functionality
- **Monitoring:** Real-time tracking of EC2 CPU and memory via CloudWatch.
- **Alerting:** CloudWatch Alarms trigger SNS notifications.
- **Self-Healing:** Alarms trigger AWS Lambda functions that securely execute SSM commands (e.g., `systemctl restart nginx`) to remediate issues.
- **Dashboard:** A React SPA that visualizes metrics, audit logs, and self-healing state.
- **Maintenance Mode:** Ability to temporarily disable self-healing actions.

## Current MVP / Existing Features
- EC2 Auto Recovery & Auto Reboot.
- High CPU alarm triggering an Nginx restart via SSM.
- Real-time dashboard showing Uptime, CPU graph, Memory graph, and Audit Logs.
- Toggle maintenance mode (disables/enables alarms).
- S3 & DynamoDB audit logging.

## Out-of-Scope Features
- Multi-region failover.
- Container orchestration (Kubernetes/ECS) - currently restricted to a single EC2 instance for simplicity.
- Complex user management (RBAC).

## Success Criteria
- 100% of detected CPU spikes or failed health checks trigger an automatic remediation.
- The dashboard accurately reflects the real-time state of the infrastructure within 10 seconds.
- The system operates entirely within the AWS Free Tier limits.
