# DarKnight MVP - Project Journal

## Frontend MVP Built (Summary)
- **Framework & Styling**: Built with Vite React, Tailwind CSS, and Shadcn UI.
- **Branding & UI**: Rebranded as "DarKnight" with a Matrix-style bootup animation featuring a 3D morphing Chandigarh Police logo.
- **Layout**: Implemented a 3-Panel Dashboard layout for general navigation, main metrics, and deep-dive details.
- **Accessibility**: Full localization (English, Hindi, Punjabi) via `react-i18next` and global Light/Dark mode toggling.
- **Key Features Implemented (with Mock Data)**:
  - **Interactive Intelligence Dashboard**: Active investigations, critical alerts, and monitored metrics.
  - **Data Collection Status**: Monitoring status of various darknet/crypto scraper nodes.
  - **Alerts & Suspicious Activity**: Feed consolidating automated alerts and AI pattern detection.
  - **Network Visualization**: Interactive, physics-based 2D network graph for suspects and crypto wallets.
  - **Search & Investigation**: Search bar with mock filtering across aliases, wallets, and keywords.
  - **Reports & Evidence**: Interface for viewing drafted/finalized reports.

## Phase 1: Security & Core Infrastructure Setup (Completed)
- **Database Architecture**: Implemented SQLAlchemy engine, declarative base, and request session management in `database.py`.
- **Core Security Models (`models.py`)**: Created ORM models matching PRD specs:
  - `User`: Email, BCrypt password hash, role hierarchy (`SUPER ADMIN / DGP` down to `CONSTABLE`), account status (`PENDING`, `ACTIVE`, `SUSPENDED`, `REJECTED`), 2FA TOTP secret, and brute-force lockout counters.
  - `RefreshSession`: Long-lived refresh session tracking with server-side revocation and IP/user-agent auditing.
  - `InvestigationAccessGrant`: Explicit delegated access grants with composite index on `(user_id, investigation_id)`.
  - `AuditLog`: Immutable append-only audit trail.
  - `DataProvenance`: Intelligence source origin, collection method, integrity hash (SHA-256), and raw record reference tracking.
- **Cryptographic Utilities (`security.py`)**: Password hashing (BCrypt cost 12), short-lived JWT Access Tokens (15 min), Refresh Tokens, Re-Authentication state tokens, TOTP MFA secret generation, and single-use 8 recovery codes.
- **Frontend Authentication Context (`AuthContext.jsx`)**: React Context provider for user session lifecycle, account status, CSRF tokens, and re-authentication modal handling.
- **Automated Verification**: Built and ran pytest test suite `tests/test_phase1_core.py` (5/5 passed cleanly).

## Phase 2: Authentication, Session Management & Governance (Completed)
- **Backend Authentication Routers (`routers/auth_router.py`)**:
  - Registration endpoint (`/signup`) with min 12-char password check, creating users in `PENDING` status.
  - Login endpoint (`/login`) with generic failure responses, 5-failed-attempt 15-minute brute-force lockout, TOTP 2FA validation, 15-min `HttpOnly` Access Token cookie, and server-side revocable Refresh Token cookie.
  - Revocable logout endpoint (`/logout`) and token refresh endpoint (`/refresh`).
  - TOTP 2FA setup (`/2fa/setup`) and verification (`/2fa/verify`) yielding secret key and 8 single-use recovery codes.
- **User Governance & Role Hierarchy (`routers/admin_router.py`)**:
  - Approvals & Role assignment (`/approve-user`) enforcing **Critical Security Constraint 4** (users cannot assign an equal or higher role than themselves).
  - Suspension endpoint (`/suspend-user`) immediately revoking all active refresh sessions.
- **Security Headers Middleware**: Configured global HTTP security headers (`HSTS`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`) in `main.py`.
- **Frontend UI Components**:
  - `LoginPage.jsx` & `RegisterPage.jsx` with DarKnight Matrix branding, error alerts, and 2FA prompts.
  - `TFAModal.jsx` for QR/secret display, recovery code copying, and verification.
  - `UserManagementTable.jsx` for Senior Officers to inspect pending users, assign role hierarchy options, and suspend users.
- **Automated Verification**: Created and ran pytest suite `tests/test_phase2_auth_gov.py` (9/9 total test cases passed cleanly).

## Phase 3: RBAC Access Control, Delegated Access & Re-Authentication (Completed)
- **Centralized Permission Matrix (`rbac.py`)**:
  - Centralized permission definitions (`READ`, `CREATE`, `UPDATE`, `DELETE`, `EXPORT`, `MANAGE_ACCESS`, `MANAGE_USERS`, `MANAGE_DATA_SOURCES`, `MANAGE_PIPELINES`, `VIEW_AUDIT_LOGS`).
  - Implemented `require_permission` FastAPI dependency checking permission matrix per role.
  - Implemented `check_investigation_modification_access()` evaluating role scope and explicit delegated grants via composite database index `(user_id, investigation_id)`.
- **Forced Re-Authentication Window (`routers/reauth_router.py` & `ReAuthModal.jsx`)**:
  - Created `/api/auth/reauthenticate` endpoint returning short-lived 10-minute re-auth token for high-risk sensitive operations.
  - Implemented `require_recent_reauth` dependency blocking sensitive operations without recent password reauth.
  - Created frontend `ReAuthModal.jsx` password confirmation dialog.
- **Delegated Access Control (`routers/delegation_router.py` & `DelegationControlPanel.jsx`)**:
  - Implemented `/grant-access` and `/revoke-access` endpoints requiring `MANAGE_ACCESS` permission + `require_recent_reauth`.
  - Enforced rules preventing users from granting access to themselves.
  - Created `DelegationControlPanel.jsx` component.
- **Automated Verification**: Created and ran pytest suite `tests/test_phase3_rbac_reauth.py` (12/12 total test cases passed cleanly).

## Phase 4: Audit Logging, Evidence Protection & Data Provenance (Completed)
- **Append-Only Audit Logging (`audit_service.py` & `routers/audit_router.py`)**:
  - Created append-only audit logger enforcing sanitization of passwords/tokens/secrets from metadata.
  - Implemented `/api/audit-logs` query endpoint filterable by date range, user ID, action, resource type, result (requires `VIEW_AUDIT_LOGS` + `require_recent_reauth`).
  - Implemented `/api/audit-logs/export` generating downloadable CSV files.
- **Evidence Protection & Integrity (`routers/evidence_provenance_router.py`)**:
  - Backend-authorized evidence stream computing SHA-256 integrity hash and returning `X-Evidence-Integrity-SHA256` header.
- **Data Provenance System (`routers/evidence_provenance_router.py` & `ProvenanceBadgePanel.jsx`)**:
  - Data provenance recording and lookup endpoints storing intelligence origin (Darknet, Telegram, Blockchain, Public Forum), collection timestamp, collection method, raw record reference, and SHA-256 hash without overwriting raw data with AI analysis.
- **Frontend UI Components**:
  - `AuditLogViewer.jsx` for Senior Officers to inspect activity logs and export CSV files.
  - `ProvenanceBadgePanel.jsx` rendering data source origin metadata, collection method, SHA-256 hash, and raw record indicator.
- **Automated Verification**: Created and ran pytest suite `tests/test_phase4_audit_evidence_provenance.py` (16/16 total test cases passed cleanly).

## Phase 5: Verification & PRD Audit (Completed)
- Conducted full PRD Definition of Done compliance check across all 15 Critical Security Constraints.
- Verified test suite execution: **16/16 test cases passed** across all 4 test modules (`test_phase1_core.py`, `test_phase2_auth_gov.py`, `test_phase3_rbac_reauth.py`, `test_phase4_audit_evidence_provenance.py`).

