# Security

Before internet-facing SaaS deployment add:
- tenant-aware PostgreSQL control plane,
- cloud/Vault secret manager,
- infrastructure egress controls,
- DNS rebinding protection,
- response/request size limits,
- PII-safe structured logs,
- quotas and audit logs,
- disabled-by-default arbitrary plugins.
