# Backlog & Tasks

## P0: Critical
- **TASK-001: Secure API Gateway**
  - **Goal:** Prevent unauthorized access to the infrastructure API.
  - **Files likely affected:** `terraform/api.tf`, `frontend/src/App.tsx`.
  - **Dependencies:** None.
  - **Acceptance criteria:** Requests without an API key or auth token are rejected (401/403). Maintenance mode cannot be toggled maliciously.
  - **Testing:** Verify unauthorized requests fail and authorized requests succeed.

## P1: High
- **TASK-002: Restrict CORS Policy**
  - **Goal:** Ensure API only accepts cross-origin requests from the known frontend host.
  - **Files likely affected:** `lambda/api.py`, `terraform/api.tf`.
  - **Dependencies:** None.
  - **Acceptance criteria:** `OPTIONS` and standard requests return strict `Access-Control-Allow-Origin` headers.
  - **Testing:** cURL requests from unauthorized origins should fail CORS checks in browsers.

- **TASK-003: Componentize Frontend Monolith**
  - **Goal:** Refactor `App.tsx` into maintainable atomic components.
  - **Files likely affected:** `frontend/src/App.tsx`, `frontend/src/components/*`.
  - **Dependencies:** None.
  - **Acceptance criteria:** UI remains visually identical, but logic is separated into `Dashboard`, `MetricCard`, `AuditList`, etc.
  - **Testing:** Verify Vite builds successfully and the dashboard functions normally.

## P2: Medium
- **TASK-004: Implement React Query for Data Fetching**
  - **Goal:** Replace `setInterval` polling with `@tanstack/react-query`.
  - **Files likely affected:** `frontend/package.json`, `frontend/src/App.tsx`, `frontend/src/services/api.ts`.
  - **Dependencies:** TASK-003 recommended.
  - **Acceptance criteria:** Dashboard polls efficiently, handles loading states properly, and prevents duplicate requests.
  - **Testing:** Verify network tab shows properly spaced polling without overlapping requests.

- **TASK-005: Add Vitest & React Testing Library**
  - **Goal:** Introduce unit testing to the frontend.
  - **Files likely affected:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/**/*.test.tsx`.
  - **Dependencies:** TASK-003.
  - **Acceptance criteria:** `npm run test` executes successfully with basic coverage for components.
  - **Testing:** Automated tests run and pass.

- **TASK-006: Add Pytest for Backend**
  - **Goal:** Introduce unit testing to Python Lambda functions.
  - **Files likely affected:** `lambda/requirements-dev.txt`, `lambda/tests/*.py`.
  - **Dependencies:** None.
  - **Acceptance criteria:** Functions can be tested locally using `moto` without hitting real AWS services.
  - **Testing:** `pytest` passes.

## P3: Low
- **TASK-007: Migrate to GitHub Actions**
  - **Goal:** Replace `deploy-frontend.sh` with a secure CI/CD pipeline.
  - **Files likely affected:** `.github/workflows/deploy.yml`.
  - **Dependencies:** None.
  - **Acceptance criteria:** Pushes to `main` automatically deploy the frontend.
  - **Testing:** Run a test pipeline execution.

- **TASK-008: Implement HTTPS / CloudFront**
  - **Goal:** Serve frontend securely via CDN rather than raw EC2 IP.
  - **Files likely affected:** `terraform/*.tf`.
  - **Dependencies:** A registered domain name.
  - **Acceptance criteria:** Dashboard is available via `https://...` and raw HTTP is redirected.
  - **Testing:** Navigate to the domain over HTTPS.
