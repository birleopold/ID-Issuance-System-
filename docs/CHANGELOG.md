# Release history

## 0.2.0 — roster and recovery improvements

- Cardholder search now supports 100-row pages and access beyond the previous 1,000-record cap.
- Added an expired-card filter and complete filtered CSV exports.
- Added administrator CSV import with a review screen, per-row errors and all-or-nothing draft creation. Imports cannot grant approval, consent or supply media.
- Backup, CSV export and PDF export preserve existing destinations until a complete new file is ready.
- Backup and restore stream database contents, avoiding a database-sized in-memory buffer.
- Restore rejects duplicate archive entries and checks essential tables and foreign-key integrity.
- Backup destinations cannot overwrite the live database, its journal, the application lock or active log.
- Print snapshots and history retain the requested sides.
- Fixed login attempt counting after an expired temporary lockout.
- Existing v0.1.0 databases and backups remain supported without a schema migration.

## 0.1.0 — initial pilot

Desktop enrollment, templates, camera/photo capture, signature capture/import, approval, native printing, print history, role controls, audit events, backup/restore and Windows installer workflow.
