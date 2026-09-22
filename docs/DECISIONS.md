# Architectural Decision Records (ADRs)

## ADR 1: Use of Serverless Lambda for API
**Decision:** Use AWS Lambda and API Gateway for the backend API instead of running a persistent web server (e.g., Flask/Django) on EC2.
**Reason:** Minimizes cost (fits in Free Tier) and offloads operational burden. The EC2 instance is reserved strictly for testing self-healing load and hosting the static asset delivery (temporarily).
**Tradeoffs:** Introduces cold starts; requires AWS-specific knowledge (API Gateway).
**Current Status:** Implemented.

## ADR 2: Direct EC2 IP Hosting for Frontend
**Decision:** Host the React SPA directly on Nginx inside the EC2 instance using its raw public IP.
**Reason:** Simplifies the MVP deployment without requiring a purchased domain name, Route53, and CloudFront.
**Tradeoffs:** Insecure (HTTP only), susceptible to IP changes (mitigated by recent updates), and poor production practice.
**Current Status:** Implemented. (Marked for future migration to S3 + CloudFront).

## ADR 3: DynamoDB for State and Auditing
**Decision:** Use DynamoDB to store the healing state and audit logs.
**Reason:** Serverless, scales to zero, fits well with Free Tier, and integrates easily with Lambda.
**Tradeoffs:** Querying capabilities are limited compared to SQL, requiring careful partition key design.
**Current Status:** Implemented.

## ADR 4: Event-Driven Self Healing
**Decision:** Use CloudWatch Alarms and EventBridge to trigger SNS, which triggers Lambda for remediation.
**Reason:** Decouples the monitoring from the remediation logic, utilizing built-in AWS async event routing.
**Tradeoffs:** Debugging requires tracing across multiple AWS services (CloudWatch -> SNS -> Lambda -> SSM).
**Current Status:** Implemented.
