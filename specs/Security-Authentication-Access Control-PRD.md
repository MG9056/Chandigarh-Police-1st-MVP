# Dark Knight — Security, Authentication & Access Control PRD

### For AI Coding Agent Execution

---

# 1. Purpose

Implement a secure authentication, authorization, auditing, session-security, and sensitive-information protection layer for the Dark Knight law-enforcement intelligence platform.

The system handles potentially sensitive investigative intelligence gathered from multiple authorized data sources. Security must therefore be enforced at the **backend**, with the frontend reflecting those permissions but never being trusted as the security boundary.

The implementation must remain **hackathon-feasible**. Do not introduce unnecessary enterprise infrastructure or security mechanisms that are not explicitly required by this PRD.

---

# 2. CRITICAL SECURITY CONSTRAINTS

These requirements are mandatory.

1. **Authentication is required for all operational application functionality.**
   - Only explicitly defined authentication/onboarding endpoints may be unauthenticated.
   - Investigation, intelligence, reports, audit logs, administration, data sources, pipelines, and other operational APIs must require authentication.

2. **Authorization MUST be enforced on the backend.**
   - Frontend hiding/disabling buttons is not a security mechanism.
   - Every protected API must independently verify the authenticated user's permissions and scope.

3. **Role hierarchy is fixed.**
   ```
   SUPER ADMIN / DGP
   IGP
   SP
   INSPECTOR
   INVESTIGATOR
   CONSTABLE
   ```
   Do not introduce Analyst, Contractor, Data Engineer, Supervisor, or other roles.

4. **Users cannot assign equal or higher roles than themselves.**

5. **All investigations are globally viewable to authenticated users unless an explicit future restriction is introduced.**
   - Modification is separately authorization-controlled.

6. **Audit logs are append-only.**
   - The application must never provide UPDATE or DELETE operations for audit logs.
   - Audit entries must not be editable through the application, including by SUPER ADMIN.

7. **Sensitive actions require recent re-authentication.**
   - A valid application session alone is insufficient for these operations.

8. **Passwords must never be stored in plaintext.**
   - Use a modern adaptive password hashing mechanism supported by the existing backend stack.

9. **Access tokens must be short-lived.**
   - Target lifetime: approximately 15 minutes.
   - Refresh tokens are longer-lived and revocable.

10. **Refresh credentials must be stored securely.**
    - Never expose refresh-token storage data unnecessarily.
    - Do not store plaintext refresh tokens in persistent storage.

11. **HTTPS/TLS is required for production communication.**

12. **Secrets must never be hardcoded or exposed to the frontend.**
    - This includes database credentials, JWT signing secrets, API keys, encryption keys, and data-source credentials.

13. **Sensitive information must not be written into application or audit logs unnecessarily.**

14. **Only lawfully obtained or appropriately authorized data sources are within system scope.**
    - Dark Knight must not implement unauthorized account access, credential theft, access-control bypassing, or interception capabilities.

15. **Original collected intelligence must not be silently overwritten by later processing.**

---

# 3. Existing Technology Context

The security implementation must integrate with the existing Dark Knight application rather than replacing its architecture.

Expected existing stack includes:

- Backend: Python / FastAPI
- Authentication: JWT-based authentication
- Database: PostgreSQL
- Frontend: React
- Existing role-based application structure
- Existing data/AI services where applicable

The AI coding agent must inspect the existing repository before implementing these features.


---

# 4. Role Hierarchy

Highest to lowest:

```text
SUPER ADMIN / DGP
        ↓
      IGP
        ↓
       SP
        ↓
   INSPECTOR
        ↓
  INVESTIGATOR
        ↓
    CONSTABLE
```

## Role assignment rule

A user may only assign a role below their own role.

Examples:

```text
DGP → IGP       ALLOWED
DGP → SP        ALLOWED
DGP → Inspector ALLOWED

IGP → SP        ALLOWED
IGP → Inspector ALLOWED
IGP → Investigator ALLOWED

SP → Inspector  ALLOWED
SP → Investigator ALLOWED
SP → Constable  ALLOWED

Inspector → Investigator ALLOWED
Inspector → Constable     ALLOWED

Investigator → Constable ALLOWED

Constable → any role      DENIED
```

No user can assign:

- Their own role
- A higher role
- SUPER ADMIN/DGP through normal user-facing APIs unless explicitly authorized by the system's initial administrative setup.

Role assignment must be audited.

---

# 5. Access-Control Model

Dark Knight uses three separate concepts:

```text
ROLE
  ↓
What operations the user is generally allowed to perform

SCOPE
  ↓
Which investigations/resources they can modify

DELEGATED ACCESS
  ↓
Additional explicitly granted access
```

These concepts must not be conflated.

## 5.1 Investigation visibility

All authenticated roles can view investigations across units.

This is intentional because investigations can be relevant across organizational boundaries.

Therefore:

```text
VIEW INVESTIGATION
→ broadly available to authenticated users
```

does NOT mean:

```text
MODIFY INVESTIGATION
→ broadly available
```

## 5.2 Default modification scope

### SUPER ADMIN / DGP

Full modification authority.

### IGP

Full modification authority.

### SP

Can modify investigations within their normal district/organizational scope.

### INSPECTOR

Can modify investigations within their assigned unit/scope.

### INVESTIGATOR

Can modify only investigations explicitly assigned/authorized to them.

### CONSTABLE

Can modify only information explicitly assigned to them and only where the relevant permission permits modification.

The exact application-specific permission matrix must be represented centrally rather than duplicated across controllers.

---

# 6. Feature Requirements

---

## S-01 — Account Signup & Approval

### What

Users can submit an account registration request.

A newly registered account must not immediately receive operational access.

The account begins in a pending state.

A higher-level authorized officer reviews the request and:

1. Approves or rejects the account.
2. Assigns the user's role.
3. Creates the appropriate access scope.

### Requirements

- Pending users cannot access operational endpoints.
- Approval must be performed by an authorized higher-level role.
- Approver cannot assign an equal or higher role.
- Approval/rejection is audit logged.
- Role assignment is audit logged.
- Account status must be checked by the backend during authentication/authorization.

Suggested account states:

```text
PENDING
ACTIVE
SUSPENDED
REJECTED
```

---

## S-02 — JWT Authentication & Session Security

### What

Implement a two-token authentication model.

```text
Access Token
→ short-lived
→ approximately 15 minutes

Refresh Token
→ longer-lived
→ used to obtain a new access token
```

### Requirements

Access tokens must contain enough information to identify the authenticated session/user but must not be treated as the sole source of current authorization.

The backend must be able to determine:

- User identity
- Account status
- Current role
- Current permissions
- Investigation scope
- Delegated access

Current backend authorization must therefore be consulted for sensitive operations.

### Refresh sessions

Maintain server-side refresh-session information sufficient to:

- Revoke a session
- Logout a user
- Revoke sessions after account suspension
- Revoke sessions after serious permission changes
- Prevent revoked refresh credentials from being reused

Do not implement refresh-token rotation unless explicitly required later.

### Password Policy

Passwords must satisfy the following requirements:

Minimum length: 12 characters.
Passwords must be hashed using BCrypt with cost factor 12.
Passwords must never be stored or logged in plaintext

### Client-Side Token Storage

Authentication tokens must be stored in secure HTTP cookies.

* Access token: HttpOnly, Secure, SameSite=Strict cookie.
* Refresh token: HttpOnly, Secure, SameSite=Strict cookie.
* Do not store access tokens or refresh tokens in localStorage, sessionStorage, IndexedDB, or other JavaScript-accessible browser storage.
* JavaScript must not have direct access to authentication tokens.
* Cookies must use appropriate expiration/max-age values matching the access-token and refresh-token lifetimes.
* Production deployment must use HTTPS so Secure cookies are transmitted only over TLS.

### CSRF Protection

Because authentication tokens are stored in cookies, protect all state-changing requests against Cross-Site Request Forgery (CSRF).

State-changing methods such as POST, PUT, PATCH, and DELETE must have CSRF protection.
Use Spring Security's built-in CSRF protection or an equivalent framework-supported mechanism.
SameSite=Strict cookies must remain enabled as an additional defense.
Do not disable CSRF protection merely because JWTs are being used.
Do not move authentication tokens to localStorage or sessionStorage as a workaround for CSRF.
The frontend must correctly include the CSRF token/header required by the backend for protected state-changing requests.
Authentication and authorization must still be enforced server-side independently of CSRF protection.

---

## S-03 — Two-Factor Authentication

### What

Implement TOTP-based MFA using a standard authenticator application.

The expected flow is:

```text
Password
   ↓
TOTP code
   ↓
Authentication complete
   ↓
Issue normal session credentials
```

### Setup

```text
User enables MFA
      ↓
Backend generates TOTP secret
      ↓
Frontend displays QR/provisioning information
      ↓
User scans with authenticator
      ↓
User enters verification code
      ↓
Backend confirms setup
```

### Requirements

- Use a standard TOTP implementation/library.
- Do not implement cryptographic TOTP generation manually.
- TOTP secret must be protected at rest.
- MFA must be required for operational user accounts according to the approved authentication policy.
- Incorrect TOTP codes must not complete authentication.
- MFA failures should be rate limited and audited.
- Do not store plaintext recovery secrets unnecessarily.

For the hackathon, avoid building an elaborate MFA recovery platform.

### TOTP Recovery

Provide a simple recovery mechanism using one-time recovery codes.

* When TOTP is enabled, generate 8 cryptographically random recovery codes.
* Display the recovery codes to the user once during setup and instruct the user to store them securely.
* Store only hashes of recovery codes in the database.
* Each recovery code can be used exactly once.
* A successfully used recovery code must be permanently invalidated.
* Recovery codes must not be returned by normal API responses after initial setup.
* Recovery-code usage must be recorded in the audit log.
* Do not implement SMS recovery, email-based MFA bypass, or an elaborate MFA recovery platform for this hackathon.

---

## S-04 — Secure Logout

### What

Logout must terminate the user's persistent authentication session rather than merely hiding the user interface.

### Requirements

On logout:

1. Revoke the server-side refresh session/token.
2. Remove authentication credentials from the client.
3. Prevent the revoked refresh credential from obtaining another access token.
4. Write a `LOGOUT` audit event.

Short-lived access tokens may remain technically valid until expiry unless the existing architecture already provides immediate access-token revocation.

Do not introduce a Redis JWT blacklist solely for logout unless the existing application architecture already requires it.

### Account suspension

When an account is suspended/deactivated:

```text
Account suspended
      ↓
Revoke active refresh sessions
      ↓
Reject future authentication
      ↓
Backend authorization denies operational access
```

---

## S-05 — Forced Re-Authentication for Sensitive Actions

### What

A user with a valid session must re-enter their password before performing high-risk operations.

This confirms that the person currently operating the session has recently demonstrated knowledge of the account credential.

### Sensitive actions include

- Assigning/changing a user's role
- Approving/rejecting an account
- Granting additional investigation access
- Revoking additional investigation access
- Suspending/reactivating users
- Viewing audit logs
- Exporting audit logs
- Generating sensitive investigation reports
- Downloading highly sensitive reports/evidence
- Adding/modifying/removing data sources
- Creating/modifying/enabling/disabling pipelines
- Resetting data nodes
- Other destructive/security-critical administrative operations

### Re-authentication window

After successful re-authentication, the user receives a short-lived re-authentication state.

Target duration:

```text
5–10 minutes
```

The user should not need to enter their password repeatedly during every related action.

### Requirements

- Backend must enforce re-authentication.
- Frontend should display a password confirmation modal when required.
- Failed re-authentication must prevent the action.
- Re-authentication attempts must be audited.
- Do not store passwords in the re-authentication token/state.

---

## S-06 — RBAC & Backend Authorization

### What

Every protected backend operation must enforce authorization.

Authorization must consider:

```text
Authenticated user
+
Role
+
Permission
+
Resource
+
Investigation scope
+
Delegated access
```

### Requirements

Controllers must not rely on frontend restrictions.

Example:

```text
Investigator sees Edit button
→ backend checks authorization
→ unauthorized request
→ HTTP 403
```

The backend must reject the request regardless of what the frontend displays.

### Permission model

Permissions should represent operations such as:

```text
READ
CREATE
UPDATE
DELETE
EXPORT
MANAGE_ACCESS
MANAGE_USERS
MANAGE_DATA_SOURCES
MANAGE_PIPELINES
VIEW_AUDIT_LOGS
```

Only permissions actually required by the application should be implemented.

Avoid creating hundreds of artificial permissions.

---

## S-07 — Delegated / Additional Investigation Access

### What

A higher-level authorized officer can explicitly grant a lower-level officer access to modify an investigation outside their normal scope.

Example:

```text
SP
 ↓
grants Investigator A
 ↓
MODIFY access
 ↓
Investigation INV-2048
```

### Requirements

Each delegated access grant must contain:

- Granting user
- Receiving user
- Investigation/resource
- Permission granted
- Creation timestamp
- Optional expiry
- Revocation state

### Rules

- A user cannot grant themselves access.
- A user cannot grant access they themselves are not authorized to grant.
- A user cannot use delegation to bypass role hierarchy.
- Grants can be revoked.
- Grants and revocations are audit logged.

---

## S-08 — Authentication Rate Limiting

### What

Protect authentication endpoints against brute-force and credential-stuffing attacks.

Rate limiting should be applied particularly to:

```text
Login
MFA verification
Refresh
Re-authentication
Signup
```

Exact thresholds should be configurable.

Example starting values:

```text
/login       → 10 requests/minute/IP
/2fa/verify  → 10 requests/minute/IP
/refresh     → 30 requests/minute/IP
/reauth      → 5 requests/minute/IP
/signup      → 10 requests/minute/IP
```

These values may be adjusted after testing.

### Requirements

- Return HTTP 429 when the limit is exceeded.
- Do not reveal unnecessary information about account existence.
- Rate limiting must be enforced server-side.
- Authentication failures should also contribute to account-level brute-force protection where appropriate.

---

## S-09 — Authentication Failure Protection

### What

Repeated failed authentication attempts should trigger temporary protection against brute-force attacks.

### Requirements

A configurable number of consecutive failed authentication attempts should temporarily lock or throttle the account.

Starting configuration:

```text
5 consecutive failures
→ temporary lockout
→ approximately 15 minutes
```

Successful authentication resets the failure counter.

The system must avoid revealing whether a particular failure occurred because of:

- nonexistent account
- incorrect password
- locked account

Use a sufficiently generic authentication failure response.

Lockout events must be audit logged.

---

## S-10 — Audit Logging

### What

Dark Knight must maintain an append-only security and activity trail.

The audit system answers:

> Who performed what action, on which resource, when, from where, and what happened?

### Events that must be logged

#### Authentication

```text
LOGIN_SUCCESS
LOGIN_FAILED
MFA_SUCCESS
MFA_FAILED
LOGOUT
ACCOUNT_LOCKED
```

#### Re-authentication

```text
REAUTH_SUCCESS
REAUTH_FAILED
```

#### Account administration

```text
ACCOUNT_CREATED
ACCOUNT_APPROVED
ACCOUNT_REJECTED
ACCOUNT_SUSPENDED
ACCOUNT_REACTIVATED
ROLE_CHANGED
```

#### Authorization

```text
ACCESS_GRANTED
ACCESS_REVOKED
ACCESS_DENIED
```

#### Investigations

```text
INVESTIGATION_CREATED
INVESTIGATION_UPDATED
INVESTIGATION_CLOSED
INVESTIGATION_DELETED
```

Only events actually supported by the application need to be emitted.

#### Evidence/reports

```text
EVIDENCE_UPLOADED
EVIDENCE_VIEWED
EVIDENCE_DOWNLOADED
REPORT_GENERATED
REPORT_DOWNLOADED
```

#### Data infrastructure

```text
DATA_SOURCE_CREATED
DATA_SOURCE_UPDATED
DATA_SOURCE_DELETED
PIPELINE_CREATED
PIPELINE_UPDATED
PIPELINE_ENABLED
PIPELINE_DISABLED
DATA_NODE_RESET
```

#### Audit operations

```text
AUDIT_LOG_VIEWED
AUDIT_LOG_EXPORTED
```

### Audit fields

Each audit event should contain, where applicable:

```text
id
timestamp
actor/user ID
actor role
action
resource type
resource ID
result
IP address
user agent/device information
session ID
metadata/context
```

### IP addresses

The request IP must be captured for security-relevant audit events.

The system must account for reverse proxies/load balancers when determining the client IP and must not blindly trust arbitrary client-supplied headers.

IP addresses are investigative/security metadata and must not be treated as proof of physical identity.

### Metadata rules

Metadata may contain contextual information such as:

```text
old role
new role
reason
investigation ID
permission granted
```

Never put the following into audit metadata:

```text
passwords
JWTs
refresh tokens
API keys
encryption keys
full confidential evidence contents
```

### Immutability

The application must provide:

```text
CREATE audit log
READ audit log
```

but not:

```text
UPDATE audit log
DELETE audit log
```

Audit records must not be editable through the application.

---

## S-11 — Audit Log Access

### What

Authorized senior users can inspect audit logs through the application.

### Requirements

Audit-log access requires:

1. Authentication
2. Appropriate permission
3. Recent re-authentication

Audit-log viewing itself generates an audit event.

### Filtering

Support practical filters such as:

- Date/time range
- User
- Action
- Resource type
- Resource ID
- Result
- Investigation ID

### Export

Audit logs may be exported by sufficiently authorized users.

Export requires:

- Authorization
- Recent re-authentication
- Audit event recording the export

Do not expose unnecessary raw metadata to users who do not have permission to see it.

---

## S-12 — Security Headers

### What

Configure standard HTTP security headers through the backend security configuration/middleware.

At minimum, evaluate and configure appropriate headers such as:

```text
Strict-Transport-Security
X-Content-Type-Options
X-Frame-Options
Content-Security-Policy
Referrer-Policy
Permissions-Policy
```

Headers must be compatible with the actual frontend application.

Do not blindly copy a restrictive CSP that breaks the application.

### Requirements

- Headers applied globally where appropriate.
- HTTPS enforcement in production.
- Authentication responses should not be unnecessarily cacheable.

---

## S-13 — Sensitive Information Protection

### What

Protect sensitive investigative information from unnecessary exposure while keeping the system practical for authorized police users.

Sensitive data masking is **not** required as a general feature because the current application does not require field-level concealment from legitimate police users.

Protection instead focuses on transmission, access, storage, and exposure.

---

### S-13.1 — Encryption in Transit

All sensitive communications must use HTTPS/TLS in production.

This includes:

```text
Frontend ↔ Backend
Backend ↔ AI service
Backend ↔ Data services
Backend ↔ External authorized data sources
```

Do not transmit credentials, tokens, investigative information, or evidence over plaintext HTTP in production.

---

### S-13.2 — Data Minimization

APIs must return only information required by the requesting operation and authorized for that user.

Do not expose:

- Internal database fields
- Credentials
- Secrets
- Unrelated investigation data
- Internal infrastructure information
- Unnecessary debugging information

The same principle applies to AI services.

If an AI operation only needs a subset of an investigation, send only that subset.

---

### S-13.3 — Evidence & File Protection

Evidence and sensitive files must never be treated as public static resources.

Requirements:

- Every evidence access/download must pass backend authorization.
- File URLs must not expose raw storage credentials or internal paths.
- A user cannot access another user's restricted evidence merely by changing an ID in a request.
- Evidence access/download must be audit logged.
- Sensitive evidence operations require re-authentication where specified.
- Deletion/destructive evidence operations require appropriate authorization.

---

### S-13.4 — Secrets Protection

The following must not be hardcoded:

```text
Database passwords
JWT signing secrets
API keys
External service credentials
Encryption keys
Data-source credentials
```

Use environment/configuration-based secret management appropriate for the deployment.

Secrets must never be:

- Returned to frontend clients
- Included in audit logs
- Included in normal API responses
- Exposed in error messages
- Committed to source control

---

## S-14 — Data Provenance

### What

Every piece of ingested intelligence must retain information about its origin.

This is particularly important for investigation review and court-facing reports.

### Minimum provenance information

Where applicable, store:

```text
Source/platform
Source identifier
Source URL or reference
Collection timestamp
Collection method
Associated investigation
Original/raw record
```

Example:

```text
Source: Darknet Marketplace X
Source Type: Darknet
Source Identifier: listing-92831
Collected At: 2026-09-03T14:25:00Z
Collection Method: Authorized automated collection
Investigation: INV-2048
```

### Requirements

- Provenance must travel with the normalized intelligence record.
- Processing must not silently destroy the original source information.
- AI-generated analysis must remain distinguishable from the original collected information.
- Reports should be able to identify the source of important intelligence.
- Collection and provenance metadata should be auditable.

---

## S-15 — Evidence Integrity & Processing History

### What

The system must maintain a distinction between:

```text
Original collected data
        ↓
Normalized/processed data
        ↓
AI analysis
        ↓
Investigator review
        ↓
Report
```

The original collected record must not simply be overwritten by AI-generated or normalized information.

### Integrity

Where practical, store an integrity hash for original collected artifacts/files.

Example:

```text
SHA-256(original artifact)
```

The hash is an integrity reference, not a substitute for legal authentication requirements.

### Requirements

- Original artifact remains recoverable where retention policy permits.
- Processing operations do not overwrite original content.
- AI analysis is clearly marked as analysis.
- Human/investigator review is distinguishable from automated analysis.
- Report generation can trace important claims back to their source records.

---

## S-16 — Frontend Security Enforcement

### What

The frontend must reflect the backend authorization model.

Frontend responsibilities:

- Hide unavailable actions.
- Disable unauthorized controls.
- Display appropriate authorization errors.
- Request re-authentication when backend indicates it is required.
- Display pending/suspended account states.
- Avoid rendering secrets or unnecessary sensitive fields.

Backend remains the authoritative security boundary.

### Example

If an Investigator cannot modify an investigation:

```text
Frontend:
Edit button hidden/disabled

Backend:
PUT /investigations/123
→ authorization check
→ 403 Forbidden
```

Both are required.

---

# 7. Recommended Core Data Models

The AI coding agent must adapt these to the existing schema rather than blindly creating duplicate entities.

## User

Required security-related information should include concepts equivalent to:

```text
id
email
password_hash
role
account_status
created_at
updated_at
mfa_enabled
mfa_secret
failed_login_attempts
locked_until
```

Additional existing user fields should remain intact.

---

## Refresh Session

Conceptually:

```text
id
user_id
refresh_token_hash
created_at
last_used_at
expires_at
revoked
ip_address
user_agent
```

Purpose:

- Refresh authentication
- Logout
- Session revocation
- Account suspension

---

## Investigation Access Grant

Conceptually:

```text
id
investigation_id
user_id
granted_by
permission
created_at
expires_at
revoked
revoked_at
```
Create a composite database index on:

(user_id, investigation_id)

This index must support authorization checks that determine whether a specific user has an explicit grant for a specific investigation.

If the implementation uses JPA/Hibernate annotations, define the composite index at the entity/table level so it is also represented in the generated database schema/migration.
---

## Audit Log

Conceptually:

```text
id
timestamp
user_id
role
action
resource_type
resource_id
result
ip_address
user_agent
session_id
metadata
```

The final schema must follow the existing database conventions.

---

## Data Provenance

Conceptually:

```text
id
source_type
source_name
source_identifier
source_url/reference
collection_method
collected_at
investigation_id
original_record_reference
integrity_hash
```

The exact model may be integrated into existing intelligence/data-source entities if that better matches the current architecture.

---

# 8. API Security Requirements

Every protected API must perform:

```text
1. Authentication
       ↓
2. Account status validation
       ↓
3. Role/permission validation
       ↓
4. Resource/scope validation
       ↓
5. Delegated-access validation where applicable
       ↓
6. Re-authentication validation for sensitive operations
       ↓
7. Execute operation
       ↓
8. Audit result
```

An authorization failure must return an appropriate HTTP 403 response.

An unauthenticated request should return HTTP 401.

Do not reveal unnecessary authorization details in error responses.

---

# 9. Sensitive Action Matrix

| Action | Authentication | Authorization | Re-auth | Audit |
|---|---|---|---|---|
| View investigation | Yes | View permission | No | Yes where appropriate |
| Modify investigation | Yes | Scope + permission | No | Yes |
| Grant investigation access | Yes | Senior authorization | Yes | Yes |
| Revoke investigation access | Yes | Senior authorization | Yes | Yes |
| Generate sensitive report | Yes | Permission | Yes | Yes |
| Download sensitive evidence | Yes | Permission | Yes where classified sensitive | Yes |
| Change user role | Yes | Higher role | Yes | Yes |
| Approve account | Yes | Higher role | Yes | Yes |
| Suspend user | Yes | Authorized senior role | Yes | Yes |
| View audit logs | Yes | Audit permission | Yes | Yes |
| Export audit logs | Yes | Authorized senior role | Yes | Yes |
| Add data source | Yes | Authorized role | Yes | Yes |
| Modify pipeline | Yes | Authorized role | Yes | Yes |
| Reset data node | Yes | Authorized administrator | Yes | Yes |
| Normal dashboard viewing | Yes | Normal permission | No | Not necessarily |
| Logout | Yes | Own session | No | Yes |

---

# 10. Security Failure Behavior

The system must distinguish:

```text
401 Unauthorized
→ no valid authentication

403 Forbidden
→ authenticated but not authorized

429 Too Many Requests
→ rate limit exceeded
```

Authentication failures should use generic messaging where revealing the precise cause could assist attackers.

Do not expose:

- Database errors
- Stack traces
- Secrets
- Token contents
- Internal infrastructure details

to normal clients.

---

# 11. Testing Requirements

The AI coding agent must add automated tests for all security-critical functionality.

## Authentication

Test:

- Valid login
- Invalid password
- Invalid MFA code
- Missing authentication
- Expired access token
- Revoked refresh session
- Suspended account
- Pending account
- Locked account

## Authorization

For each role:

- Test allowed operations.
- Test denied operations.
- Test equal/higher role assignment rejection.
- Test investigation scope.
- Test delegated access.
- Test revoked delegated access.
- Test attempts to bypass scope using modified IDs/query parameters.

## Forced Re-authentication

Test:

- Sensitive action without re-auth → rejected.
- Valid re-auth → action permitted.
- Expired re-auth state → rejected.
- Incorrect password → rejected.
- Re-authentication failure → audit event.
- Sensitive action after successful re-auth → audit event.

## Audit Logs

Test:

- Successful actions create logs.
- Failed security actions create logs.
- Denied authorization attempts create logs.
- IP address is captured.
- Logout is logged.
- Audit-log viewing is logged.
- Audit-log export is logged.
- Audit records cannot be updated.
- Audit records cannot be deleted.
- Sensitive credentials do not appear in audit data.

## Rate Limiting

Test:

- Limit is enforced.
- HTTP 429 returned.
- Normal requests resume after the limit window.
- Authentication endpoints are protected.

## Evidence

Test:

- Unauthorized evidence access rejected.
- ID manipulation cannot bypass authorization.
- Evidence download is logged.
- Sensitive evidence operation requires re-authentication where configured.

## Provenance

Test:

- Source metadata is stored.
- Collection timestamp is retained.
- Original record is preserved.
- AI processing does not overwrite original source information.
- Report generation can identify source information.

---

# 12. Implementation Order

Implement in the following order unless repository dependencies require a minor adjustment.

```text
1. Inspect existing authentication/security architecture

2. Establish/clean up User + Role + Account Status model

3. Implement/strengthen password authentication

4. Implement JWT access + refresh session architecture

5. Implement secure logout/session revocation

6. Implement TOTP MFA

7. Implement authentication failure protection + rate limiting

8. Implement centralized RBAC/permission checking

9. Implement investigation scope authorization

10. Implement delegated investigation access

11. Implement forced re-authentication

12. Implement audit logging infrastructure

13. Wire audit logging into security/investigation operations

14. Implement security headers

15. Implement sensitive information protection requirements

16. Implement evidence authorization/protection

17. Implement data provenance + evidence integrity

18. Update frontend authorization behavior

19. Add comprehensive security tests

20. Run full application test suite and security regression tests
```

---

# 13. Definition of Done

The implementation is complete only when:

- All operational endpoints require authentication.
- Backend authorization cannot be bypassed through frontend manipulation.
- Role hierarchy is enforced.
- Users cannot self-elevate.
- Investigation visibility and modification authorization are separated.
- Delegated investigation access works and is revocable.
- JWT authentication works with short-lived access tokens.
- Refresh sessions can be revoked.
- Logout actually invalidates the persistent refresh session.
- MFA works using TOTP.
- Authentication endpoints are rate limited.
- Repeated authentication failures trigger appropriate protection.
- Sensitive actions require recent re-authentication.
- Audit events are generated for defined security-sensitive operations.
- Audit logs cannot be modified or deleted through the application.
- Audit logs contain IP/session/request metadata where applicable.
- HTTPS/TLS is enforced for production communications.
- Security headers are configured.
- Secrets are not hardcoded or exposed.
- APIs minimize unnecessary sensitive data.
- Evidence cannot be accessed without backend authorization.
- Intelligence retains source provenance.
- Original collected records are distinguishable from processed/AI-generated analysis.
- Security-critical behavior has automated tests.
- No unauthorized collection/interception functionality is introduced.

---

# 14. Explicit Non-Goals

Do NOT implement the following unless explicitly requested later:

- Contractor role
- Analyst role
- Data Engineer role
- Supervisor role
- Custom user-created roles
- Refresh-token rotation
- Redis JWT blacklist solely for logout
- Complex device/session management
- IP geolocation and automatic geographic blocking
- Sensitive-field masking as a general requirement
- SMS-based MFA
- Custom cryptographic algorithms
- Blockchain-based audit logs
- Unauthorized account access
- Credential theft
- Bypassing platform authentication
- Communication interception
- Decryption of communications without appropriate authorization
- Enterprise SIEM functionality
- Overly complex security infrastructure unsuitable for the hackathon

---

# 15. Security Design Principle

The overall Dark Knight security model should follow:

```text
                    AUTHENTICATION
                          ↓
                  "Who are you?"
                          ↓
                       ROLE
                          ↓
                 "What can you do?"
                          ↓
                       SCOPE
                          ↓
             "Where can you do it?"
                          ↓
                 DELEGATED ACCESS
                          ↓
        "Has additional access been granted?"
                          ↓
                 SENSITIVE ACTION?
                    /           \
                  NO             YES
                  ↓               ↓
              Execute        RE-AUTHENTICATE
                                  ↓
                              Execute
                                  ↓
                            AUDIT EVENT
```

The system should follow the principle:

> **Trust as little as necessary, authorize as specifically as necessary, and record security-relevant actions so they can be investigated later.**