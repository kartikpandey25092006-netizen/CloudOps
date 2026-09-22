# AI Development Rules (Vibe Coding Principles)

When contributing to this project, adhere to the following rules:

## 1. Documentation First
- Read relevant documentation (e.g., `ARCHITECTURE.md`, `PRD.md`) before modifying code.
- Keep `MEMORY.md` and `TASKS.md` updated after meaningful changes.
- Do not silently change architectural decisions. Update `DECISIONS.md` if a change is justified.

## 2. Code Modification
- Inspect existing implementation before creating new functionality.
- Reuse existing components and utilities. Do not duplicate logic.
- Do not create parallel implementations of existing functionality.
- Keep changes focused. Prefer the smallest safe change.
- Do not modify unrelated files.

## 3. Architecture & Tech Stack
- Follow the existing architecture. 
- Do not replace technologies (e.g., switching from Vite to Next.js) without explicit justification and user approval.
- Do not create unnecessary abstractions.

## 4. Security & Safety
- **Never expose secrets.** Always use environment variables.
- Verify authorization server-side. Do not trust client-side authorization.
- Validate all user input.
- Handle errors explicitly and return standardized, sanitized error messages. Do not leak stack traces.

## 5. UI / UX
- Add appropriate loading, error, and empty states for all async operations.
- Maintain responsive design and accessibility.
- Follow the visual guidelines in `DESIGN.md`.

## 6. Testing & Validation
- Never claim something works without verifying it.
- Run relevant tests, type checks, and linting after changes.
- Ensure the application builds successfully before committing.

## 7. Workflow
- Always follow: READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT-READY -> UPDATE DOCS.
- Never jump directly from REQUEST to CODE. Wait for approval on large architectural changes.
