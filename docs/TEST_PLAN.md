# Test Plan

Currently, the project lacks automated testing. This document outlines the testing requirements for future development.

## 1. Authentication & Authorization
- **Status:** Unimplemented.
- **Future Tests:** 
  - Verify unauthenticated requests to `/api/*` return 401 Unauthorized.
  - Verify authenticated requests with incorrect roles return 403 Forbidden.

## 2. Core Business Logic (Backend)
- **Framework:** `pytest` with `moto` (AWS mocking).
- **Tests Needed:**
  - Mock DynamoDB and test `get_audit_logs()` and `get_healing_state()`.
  - Mock CloudWatch and test `get_cpu_metrics()` parsing and padding.
  - Test `main.py` (Remediation Lambda) triggering correct SSM commands when SNS event is passed.
  - Test `health_manager.py` dynamic IP fetching logic.

## 3. Frontend (React)
- **Framework:** `Vitest` and `React Testing Library`.
- **Tests Needed:**
  - Render metric cards correctly given mock API data.
  - Ensure Maintenance Mode toggle sends correct POST request and updates UI optimistically.
  - Test conditional rendering of Audit Log colors (Red for error, Blue for success).

## 4. APIs
- **Tests Needed:**
  - Validate response schema of `/api/status`.
  - Validate error handling when AWS services (like CloudWatch) throttle or fail.

## 5. E2E User Flows
- **Framework:** `Playwright` or `Cypress` (Future).
- **Flows:**
  - User loads dashboard -> Data is fetched -> Graph renders.
  - User clicks Maintenance Mode -> Confirmation -> Backend state changes.

## 6. Infrastructure
- **Tests Needed:**
  - Load testing using the existing `load-tests/` k6 scripts to verify CloudWatch alarms fire under heavy CPU/Memory load.
