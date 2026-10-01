# Security and operational model

## Trust boundary

This application is intended for a trusted, managed Windows workstation. It is not a network service. Application roles protect ordinary operator workflows but do not protect against an OS administrator or a user who can edit the database directly. The SQLite database, exported PDFs, CSV files and backups are unencrypted. Use restricted Windows accounts, device encryption, managed backups and an appropriate retention policy. The implementation does not claim compliance certification.

## Implemented controls

- Unique salted scrypt password hashes, minimum 12-character passwords, constant-time hash comparison.
- Persistent failed-attempt counters and a 15-minute account lock after five failures.
- No default credentials, no hardcoded master password, no recovery bypass.
- Administrator/operator checks in service operations, rechecked against the active account.
- Single instance per data directory; parameterized SQL; database transactions and foreign keys.
- Optimistic versions for record edits and print preparation.
- Explicit approval, reasoned revisions/revocation, no silent changes to issued records.
- Unresolved-job exclusion to prevent accidental duplicate submissions.
- Saved rendered print snapshots with template data and image SHA-256 values.
- Append-only audit triggers for ordinary application/SQL updates. These are not cryptographic tamper evidence.
- Local session lock and reauthentication; no network transfer of enrollment data.
- Data-only template JSON; bounded files/coordinates; no template code evaluation.
- Spreadsheet-formula neutralization in CSV exports.
- Schema version checks and restore refusal for existing databases.

## Known limits and next hardening decisions

- No separation-of-duty requirement: an administrator may enroll and approve the same card. Add a second-reviewer policy if the customer requires it.
- No field-level encryption, key recovery service, remote audit archive, signed verification QR or cryptographic card validation.
- Capture authorization is a recorded checkbox, not a complete consent-management system.
- No record purge/retention UI. Agree on a data retention/deletion implementation before a deployment requiring automated erasure.
- Application logs intentionally contain only error classes. Hardware troubleshooting may require separate vendor logs, which need privacy review before sharing.
- No automated security updates or signed updater. Release upgrades are deployed by the administrator/technician using a tested installer.
- Password recovery depends on controlled account planning and backups; do not edit hashes manually in customer operations.

## Reporting

Report security concerns privately to the repository owner before publishing identity data or exploitation details in an issue. A formal customer support/security contact must be agreed before commercial handover.
