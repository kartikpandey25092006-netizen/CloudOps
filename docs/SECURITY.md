# Security Requirements

## 1. Authentication & Authorization
- **Current State:** The API Gateway is completely open. Unauthenticated users can view infrastructure metrics and toggle maintenance mode.
- **Requirement:** Implement API Gateway authorization. Depending on complexity, this should either be a static API Key (for a single Ops user) or AWS Cognito / IAM authentication for role-based access.

## 2. Secrets Management
- No hardcoded secrets should exist in the codebase.
- Environment variables must be loaded via `.env` (excluded from git) or passed through CI/CD secure variables.
- Terraform must not output sensitive credentials in plaintext where avoidable.

## 3. Input Validation
- The `POST /api/maintenance` endpoint must strictly validate the incoming JSON body. It currently trusts the input shape blindly, which could lead to exceptions.

## 4. Database Security
- IAM Roles for Lambda must continue adhering to the principle of least privilege.
- Ensure that the Lambda functions only have access to specific DynamoDB tables, and cannot scan the entire database.

## 5. API Validation & CORS
- The API currently returns `Access-Control-Allow-Origin: *`.
- **Requirement:** Update the CORS headers in `api.py` and Terraform to strictly allow only the specific domain hosting the React frontend.

## 6. Network & Transport Security
- The frontend is served over HTTP via the EC2 instance's IP.
- **Requirement:** Implement HTTPS using a custom domain and AWS Certificate Manager (ACM) via CloudFront or an Application Load Balancer.

## 7. Error Leakage
- Backend errors currently leak raw exception strings: `{"error": str(e)}`.
- **Requirement:** Catch expected exceptions and return standardized, sanitized error messages to the client. Do not leak internal stack traces or database structure details.
