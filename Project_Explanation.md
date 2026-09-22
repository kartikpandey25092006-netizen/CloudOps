# Self-Healing Cloud Infrastructure

## What is this project?
This project is an automated, **"Self-Healing" Cloud Architecture** built on Amazon Web Services (AWS). 

Normally, if a server crashes or gets overwhelmed by traffic, a human engineer has to wake up in the middle of the night, log into the server, and fix it (for example, by restarting the web server or rebooting the machine). 

This project completely automates that process using a combination of AWS tools. If something goes wrong, the system detects it and fixes itself instantly—without human intervention.

---

## How does it work?
The architecture relies on a few key AWS services working together to form "Self-Healing Loops":

### 1. The Watchdog (Amazon CloudWatch)
CloudWatch constantly monitors the health and performance of our web server (an EC2 instance running Nginx). It watches metrics like CPU usage and system health status. 

### 2. The Trigger (Amazon SNS & EventBridge)
If the CPU spikes above 75% for too long, or if the server stops responding, CloudWatch triggers an Alarm. This alarm sends a signal through Amazon SNS (Simple Notification Service) and instantly emails the DevOps team that a failure occurred.

### 3. The Healer (AWS Lambda & Systems Manager)
Instead of waiting for a human to read the email, the alarm automatically triggers an **AWS Lambda function** (a serverless Python script). 
* If the web server application is stuck (high CPU), the Lambda function uses **AWS Systems Manager (SSM)** to securely reach inside the server and run a command to restart the Nginx web service, fixing the issue instantly.
* If the actual virtual hardware fails, AWS automatically migrates the server to healthy hardware.

### 4. The Dashboard & Audit Trail (React & S3)
* Every time a self-healing action occurs, the system writes a detailed audit log to an **Amazon S3 Bucket** so the engineers can review what happened the next morning.
* A live **React Frontend Dashboard** (which you can view in your browser) visualizes the real-time health of the system, showing server uptime, CPU metrics, and recent alarm statuses.

---

## Summary
In short, this project demonstrates advanced **Cloud Operations (CloudOps)** and **Site Reliability Engineering (SRE)**. It takes a standard web server and wraps it in a protective, automated layer of monitoring and remediation, ensuring maximum uptime and reliability!
