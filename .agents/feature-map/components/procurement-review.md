# Procurement review

A CE-path extension. The Next.js admin page submits structured evidence references to the FastAPI router; SQLAlchemy Core stores the immutable payload and versioned review/audit state in the current tenant session. Migration sl20261023a follows c5178de73522; Alembic target metadata includes procurement_metadata.

Entry points: `/admin/procurement` frontend, `/admin/procurement` API under the deployment's API prefix. All API endpoints use require_permission(FULL_ADMIN_PANEL_ACCESS). Only the author can submit; a different authorized user can approve/reject. Every administrator in that tenant may list/read reviews. No custom project-scoped permission is implied.

Invariants: no legacy role checks; no anonymous exemption; existing PAT scope enforcement and tenant-aware get_session preserved; unique owner/request-key binds payload; conditional state/version update and audit insert share a transaction; mandatory valid evidence is checked at submit and approve; evidence refs do not grant document access. No export or downstream write endpoint.

Verification: enterprise/tests/test_procurement.py with CI PostgreSQL, frontend type check. Full app startup router-auth check, migration in a multi-tenant deployment and browser two-account UAT remain integration requirements. The auth-and-identity section-5 invariants remain unchanged: no credentials, OAuth/SCIM/logout/consent changes, no User.role reads and no PAT bypass. Database administrators can still mutate tables outside this API.
