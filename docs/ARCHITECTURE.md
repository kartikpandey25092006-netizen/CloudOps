# Architecture Document

## CURRENT Architecture

### Frontend
- **Framework:** React 18 (SPA) built with Vite.
- **Styling:** Tailwind CSS (via `index.css`), Lucide React icons, Recharts for graphs.
- **Hosting:** Static files synced to S3 and served directly by Nginx on an EC2 `t3.micro` instance using its raw public IP.
- **Data Fetching:** Polls API Gateway every 10 seconds via `setInterval`.

### Backend
- **Framework:** Python 3.11/3.12 AWS Lambda functions.
- **APIs:** AWS API Gateway routing to `lambda/api.py`.
- **Background Jobs:** 
  - `health_manager.py`: Triggered by EventBridge cron.
  - `main.py`: Triggered by SNS (from CloudWatch Alarms or EventBridge state changes).

### Database & Storage
- **DynamoDB:** Stores `self-healing-logs` and `self-healing-state`.
- **S3:** Stores frontend assets and archived audit logs.

### Authentication
- **Current State:** None. The API Gateway is fully public.

### External Services
- **AWS CloudWatch:** Metrics collection and Alarms.
- **AWS SNS:** Notifications and triggering Lambdas.
- **AWS SSM:** Systems Manager Run Command for executing bash scripts on EC2 securely.

### Deployment
- Infrastructure managed via Terraform (`/terraform`).
- Frontend deployment managed by a local bash script (`deploy-frontend.sh`).

### Data Flow
1. **Metrics:** EC2 (CloudWatch Agent) -> CloudWatch -> API Gateway -> React Dashboard.
2. **Remediation:** CloudWatch Alarm -> SNS -> Lambda (`main.py`) -> SSM -> EC2.
3. **Audit Logging:** Lambda -> DynamoDB & S3.

---

## RECOMMENDED Future Improvements

- **API Security:** Secure API Gateway with an API Key or Cognito authorizer.
- **Frontend Hosting:** Migrate from EC2 Nginx serving to S3 + CloudFront (CDN) with a custom domain and HTTPS.
- **Data Fetching:** Replace manual `setInterval` polling with React Query (TanStack Query) or WebSockets.
- **CI/CD:** Replace local bash scripts with GitHub Actions pipelines for automated Terraform and Vite builds.
- **Componentization:** Refactor the monolithic `App.tsx` into atomic components.
