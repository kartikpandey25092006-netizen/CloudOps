# AWS Self-Healing Infrastructure

## Overview
This document outlines the enterprise-grade self-healing and automation features deployed within the AWS environment. The architecture is designed to survive software bugs, OS crashes, and physical hardware failures with zero human intervention.

---

### 1. Software-Level Self Healing (CPU Spike Remediation)
* **Trigger:** A CloudWatch Alarm monitors the EC2 server. If the CPU utilization exceeds 75% (indicating a rogue process, traffic spike, or hanging software like Nginx), the alarm triggers.
* **Mechanism:** The alarm publishes to an SNS topic, which invokes a serverless **AWS Lambda function**.
* **Action:** The Lambda function uses AWS Systems Manager (SSM) to securely connect to the EC2 instance and forcefully restart the web server process, instantly restoring health.

### 2. Hardware-Level Auto-Recovery
* **Trigger:** AWS constantly monitors the physical underlying hardware in the data center. If the physical motherboard, power supply, or network interface fails (`StatusCheckFailed_System`), an alarm is triggered.
* **Mechanism & Action:** CloudWatch automatically migrates the EC2 instance to a brand new, healthy physical machine while retaining the exact same IP address, volumes, and configuration.

### 3. OS-Level Auto-Reboot
* **Trigger:** If the server's Operating System experiences a kernel panic, runs completely out of memory, or the network driver crashes (`StatusCheckFailed_Instance`), a CloudWatch Alarm detects the unresponsiveness.
* **Mechanism & Action:** CloudWatch automatically forces a hard hardware-level reboot to kick the Operating System back online.

### 4. Immutable Audit Logging (S3)
* **Mechanism:** Automated remediation must be tracked. Every time the self-healing Lambda function intervenes to heal your server, it generates a detailed log file.
* **Action:** These timestamped logs are written directly into an encrypted, version-controlled **Amazon S3 Bucket**. This allows operations teams to perform root-cause analysis the next morning.

### 5. Fail-Safe "Watch the Watcher" Alarm
* **Trigger:** A dedicated CloudWatch Alarm monitors the self-healing Lambda function itself.
* **Mechanism & Action:** If the Lambda function throws an error or fails to execute properly, it triggers a separate Ops Notification alert. This ensures the operations team knows immediately if the automated healing mechanism is broken.

### 6. Centralized CloudWatch Dashboard
* **Mechanism:** All metrics, alarms, and system health statuses are aggregated into a single pane of glass.
* **Action:** Provides immediate visibility into the real-time state of the infrastructure without needing to navigate through multiple AWS console screens.
