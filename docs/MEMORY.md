# Project Memory

## Current Phase
Phase 3/4: Context Documentation & Planning

## Completed Work
- Completed Phase 1 Audit of the existing infrastructure.
- Generated project documentation (`PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `TEST_PLAN.md`, `SECURITY.md`, `DECISIONS.md`).
- Documented rules and tasks.

## Current Task
- Finalizing the documentation structure before moving to Phase 4 (Executing improvement tasks).

## Known Issues
- API endpoints are unauthenticated.
- Frontend uses `setInterval` which is inefficient.
- Frontend is a monolith (`App.tsx`).
- No HTTPS.

## Recent Changes
- Updated EC2 Terraform config to ignore AMI changes to prevent accidental instance replacement.
- Updated Health Manager Lambda to dynamically fetch EC2 public IP.

## Next Recommended Task
- **TASK-001:** Secure the API Gateway endpoints.
