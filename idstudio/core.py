"""Persistence and authorization. UI actions must go through this service."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


class DomainError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_directory():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "CredentialStudio"


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"{salt}:{digest}"


def validate_password(password):
    if len(password) < 12 or len(password) > 256:
        raise DomainError("Use a password between 12 and 256 characters.")


class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.folder / "studio.db")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        if self.db.execute("PRAGMA user_version").fetchone()[0] > 1:
            raise DomainError("This database needs a newer version of Credential Studio.")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','operator')),
          active INTEGER NOT NULL DEFAULT 1, failures INTEGER NOT NULL DEFAULT 0,
          locked_until TEXT);
        CREATE TABLE IF NOT EXISTS records (
          id TEXT PRIMARY KEY, card_no TEXT NOT NULL UNIQUE COLLATE NOCASE,
          full_name TEXT NOT NULL, department TEXT NOT NULL, title TEXT NOT NULL,
          expires TEXT NOT NULL, template TEXT NOT NULL, photo BLOB, signature BLOB,
          consent INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft'
          CHECK(status IN ('draft','approved','issued','revoked')),
          version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, record_id TEXT NOT NULL REFERENCES records(id),
          snapshot TEXT NOT NULL, front BLOB NOT NULL, back BLOB NOT NULL,
          printer TEXT NOT NULL, status TEXT NOT NULL
          CHECK(status IN ('prepared','submitted','confirmed','failed','uncertain')),
          reason TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL,
          action TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
          BEGIN SELECT RAISE(ABORT, 'Audit events cannot be edited'); END;
        CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
          BEGIN SELECT RAISE(ABORT, 'Audit events cannot be deleted'); END;
        CREATE TABLE IF NOT EXISTS templates (name TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        PRAGMA user_version=1;
        """)
        self.user = None

    @contextmanager
    def transaction(self):
        # Nested service calls participate in the outer operation atomically.
        savepoint = "sp_" + uuid.uuid4().hex if self.db.in_transaction else None
        try:
            self.db.execute(f"SAVEPOINT {savepoint}" if savepoint else "BEGIN IMMEDIATE")
            yield
            if savepoint:
                self.db.execute(f"RELEASE SAVEPOINT {savepoint}")
            else:
                self.db.commit()
        except Exception:
            if savepoint:
                self.db.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self.db.execute(f"RELEASE SAVEPOINT {savepoint}")
            else:
                self.db.rollback()
            raise

    def audit(self, action, target="", detail=""):
        self.db.execute("INSERT INTO audit(at,actor,action,target,detail) VALUES(?,?,?,?,?)",
                        (now(), self.user["username"] if self.user else "system", action, target, detail))

    def authorize(self, admin=False):
        if not self.user:
            raise DomainError("Sign in to continue.")
        current = self.db.execute("SELECT * FROM users WHERE id=?", (self.user["id"],)).fetchone()
        if not current or not current["active"] or (admin and current["role"] != "admin"):
            raise DomainError("This action requires an active administrator account." if admin else "Account disabled.")
        self.user = dict(current)

    def has_users(self):
        return bool(self.db.execute("SELECT 1 FROM users LIMIT 1").fetchone())

    def create_user(self, username, password, role="operator"):
        username = username.strip()
        if not 3 <= len(username) <= 60 or role not in ("admin", "operator"):
            raise DomainError("Enter a username of 3–60 characters and a valid role.")
        validate_password(password)
        with self.transaction():
            if self.has_users():
                self.authorize(admin=True)
            elif role != "admin":
                raise DomainError("The first account must be an administrator.")
            try:
                self.db.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                                (username, password_hash(password), role))
            except sqlite3.IntegrityError as exc:
                raise DomainError("That username already exists.") from exc
            self.audit("account.created", username, role)

    def login(self, username, password):
        self.user = None
        with self.transaction():
            row = self.db.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
            if row and row["locked_until"] and row["locked_until"] > now():
                raise DomainError("Account temporarily locked. Try again in 15 minutes.")
            # Perform the same expensive KDF for unknown users.
            saved = row["password"] if row else "00" * 16 + ":" + "00" * 64
            valid = hmac.compare_digest(password_hash(password[:257], saved.split(":")[0]), saved)
            if not row or not valid or not row["active"]:
                if row:
                    failures = (0 if row["locked_until"] else row["failures"]) + 1
                    until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(timespec="seconds") if failures >= 5 else None
                    self.db.execute("UPDATE users SET failures=?,locked_until=? WHERE id=?", (failures, until, row["id"]))
                self.audit("login.failed")
            else:
                self.db.execute("UPDATE users SET failures=0,locked_until=NULL WHERE id=?", (row["id"],))
                self.user = dict(row)
                self.audit("login.success")
        if not self.user:
            raise DomainError("Username or password incorrect, or account disabled.")

    def change_password(self, current, replacement):
        self.authorize()
        validate_password(replacement)
        saved = self.user["password"]
        if not hmac.compare_digest(password_hash(current, saved.split(":")[0]), saved):
            raise DomainError("Current password is incorrect.")
        with self.transaction():
            self.db.execute("UPDATE users SET password=? WHERE id=?", (password_hash(replacement), self.user["id"]))
            self.audit("password.changed", str(self.user["id"]))

    def set_active(self, user_id, active):
        self.authorize(admin=True)
        if user_id == self.user["id"]:
            raise DomainError("You cannot disable your own account.")
        with self.transaction():
            self.db.execute("UPDATE users SET active=? WHERE id=?", (int(active), user_id))
            self.audit("account.enabled" if active else "account.disabled", str(user_id))

    def validate_record(self, values):
        self.authorize()
        fields = ["card_no", "full_name", "department", "title", "expires", "template", "photo", "signature", "consent"]
        clean = {k: values.get(k) for k in fields}
        for key in fields[:6]:
            clean[key] = str(clean[key] or "").strip()
            if len(clean[key]) > 160:
                raise DomainError(f"{key.replace('_', ' ').title()} is too long (160 characters maximum).")
        if not clean["card_no"] or not clean["full_name"]:
            raise DomainError("Full name and card number are required.")
        try:
            if date.fromisoformat(clean["expires"]).isoformat() != clean["expires"]:
                raise ValueError("Noncanonical date")
        except ValueError as exc:
            raise DomainError("Choose a valid expiry date in YYYY-MM-DD format.") from exc
        if not self.db.execute("SELECT 1 FROM templates WHERE name=?", (clean["template"],)).fetchone():
            raise DomainError("Choose an existing card template.")
        for media in ("photo", "signature"):
            blob = clean[media]
            if blob is not None and (not isinstance(blob, bytes) or len(blob) > 8_000_000):
                raise DomainError("Image data must be at most 8 MB.")
        clean["consent"] = int(bool(clean["consent"]))
        return clean

    def save_record(self, values, record_id=None, version=None):
        clean = self.validate_record(values)
        fields = list(clean)
        record_id = record_id or str(uuid.uuid4())
        try:
            with self.transaction():
                old = self.db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
                if old:
                    if old["status"] != "draft":
                        raise DomainError("Only drafts can be edited. Return an approved card to draft first.")
                    if old["version"] != version:
                        raise DomainError("This record changed. Reload it before saving.")
                    self.db.execute("UPDATE records SET " + ",".join(f"{k}=?" for k in fields) +
                                    ",version=version+1,updated_at=? WHERE id=?", (*clean.values(), now(), record_id))
                else:
                    self.db.execute("INSERT INTO records(id," + ",".join(fields) + ",created_at,updated_at) VALUES(" +
                                    ",".join("?" for _ in range(12)) + ")", (record_id, *clean.values(), now(), now()))
                self.audit("record.saved", record_id)
        except sqlite3.IntegrityError as exc:
            raise DomainError("That card number is already in use.") from exc
        return record_id

    def get_record(self, record_id):
        self.authorize()
        row = self.db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise DomainError("Record not found.")
        return dict(row)

    def record_filter(self, search, status):
        if status not in ("all", "draft", "approved", "issued", "revoked", "expired"):
            raise DomainError("Unknown record filter.")
        clause = "(instr(lower(full_name),lower(?))>0 OR instr(lower(card_no),lower(?))>0)"
        args = [search, search]
        if status == "expired":
            clause += " AND expires < ? AND status != 'revoked'"
            args.append(date.today().isoformat())
        elif status != "all":
            clause += " AND status=?"
            args.append(status)
        return clause, args

    def record_count(self, search="", status="all"):
        self.authorize()
        clause, args = self.record_filter(search, status)
        return self.db.execute("SELECT count(*) FROM records WHERE " + clause, args).fetchone()[0]

    def records(self, search="", status="all", limit=1000, offset=0):
        self.authorize()
        if not isinstance(limit, int) or not 1 <= limit <= 1000 or not isinstance(offset, int) or offset < 0:
            raise DomainError("Invalid page size or offset.")
        clause, args = self.record_filter(search, status)
        return self.db.execute("SELECT id,card_no,full_name,department,expires,status,version FROM records WHERE " +
                               clause + " ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()

    def export_records(self, search="", status="all"):
        """Cursor over all matches, without loading media or truncating at a UI limit."""
        self.authorize(admin=True)
        clause, args = self.record_filter(search, status)
        return self.db.execute("SELECT card_no,full_name,department,expires,status FROM records WHERE " +
                               clause + " ORDER BY updated_at DESC,id DESC", args)

    def import_drafts(self, rows, template):
        self.authorize(admin=True)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
            raise DomainError("Import between 1 and 1,000 rows per batch.")
        ids = []
        with self.transaction():
            for index, row in enumerate(rows, 1):
                # Only identity text is accepted. CSVs cannot assign approval,
                # consent, images, paths, IDs or existing-record updates.
                values = {key: row.get(key, "") for key in ("card_no", "full_name", "department", "title", "expires")}
                values.update(template=template, photo=None, signature=None, consent=False)
                try:
                    ids.append(self.save_record(values))
                except DomainError as exc:
                    raise DomainError(f"Import row {index}: {exc}. Nothing was imported.") from exc
            self.audit("records.imported", detail=f"{len(ids)} drafts")
        return ids

    def preflight(self, record):
        problems = []
        if date.fromisoformat(record["expires"]) < date.today():
            problems.append("Expiry date is in the past")
        if not record["photo"]:
            problems.append("Photo is missing")
        if not record["signature"]:
            problems.append("Signature is missing")
        if not record["consent"]:
            problems.append("Capture authorization has not been recorded")
        return problems

    def transition(self, record_id, target, reason=""):
        self.authorize(admin=True)
        with self.transaction():
            record = self.get_record(record_id)
            allowed = {("draft", "approved"), ("approved", "draft"), ("issued", "revoked"), ("approved", "revoked")}
            if (record["status"], target) not in allowed:
                raise DomainError("That status change is not allowed.")
            if self.db.execute("SELECT 1 FROM jobs WHERE record_id=? AND status IN ('prepared','submitted','uncertain')", (record_id,)).fetchone():
                raise DomainError("Resolve the pending print job first.")
            if target == "approved" and (problems := self.preflight(record)):
                raise DomainError("; ".join(problems))
            if target != "approved" and not reason.strip():
                raise DomainError("A reason is required for this change.")
            self.db.execute("UPDATE records SET status=?,version=version+1,updated_at=? WHERE id=?", (target, now(), record_id))
            self.audit("record." + target, record_id, reason[:500])

    def prepare_job(self, record_id, version, front, back, printer, reason="", sides="both"):
        self.authorize()
        if sides not in ("front", "back", "both"):
            raise DomainError("Choose front, back or both sides.")
        if not front or not back or not printer.strip():
            raise DomainError("A rendered card and printer are required.")
        with self.transaction():
            record = self.get_record(record_id)
            if record["version"] != version:
                raise DomainError("Record changed. Reload before printing.")
            if record["status"] not in ("approved", "issued"):
                raise DomainError("An administrator must approve the card before printing.")
            if problems := self.preflight(record):
                raise DomainError("; ".join(problems))
            if self.db.execute("SELECT 1 FROM jobs WHERE record_id=? AND status IN ('prepared','submitted','uncertain')", (record_id,)).fetchone():
                raise DomainError("Resolve the existing print job before printing again.")
            if record["status"] == "issued":
                self.authorize(admin=True)
                if not reason.strip():
                    raise DomainError("An administrator must enter a reprint reason.")
            job_id = str(uuid.uuid4())
            snapshot = {k: v for k, v in record.items() if k not in ("photo", "signature")}
            snapshot["template_body"] = json.loads(self.db.execute("SELECT body FROM templates WHERE name=?", (record["template"],)).fetchone()[0])
            snapshot["front_sha256"] = hashlib.sha256(front).hexdigest()
            snapshot["back_sha256"] = hashlib.sha256(back).hexdigest()
            snapshot["sides"] = sides
            self.db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (job_id, record_id, json.dumps(snapshot), front, back, printer, "prepared", reason[:500], now(), now()))
            self.audit("print.prepared", job_id, record_id)
        return job_id

    def finish_job(self, job_id, target, detail=""):
        self.authorize()
        with self.transaction():
            job = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            allowed = {("prepared", "submitted"), ("prepared", "uncertain"), ("prepared", "failed"),
                       ("submitted", "confirmed"), ("submitted", "failed"), ("uncertain", "confirmed"), ("uncertain", "failed")}
            if not job or (job["status"], target) not in allowed:
                raise DomainError("That print status change is not allowed.")
            if target in ("confirmed", "failed") and not detail.strip():
                raise DomainError("Record the physical print outcome.")
            self.db.execute("UPDATE jobs SET status=?,updated_at=? WHERE id=?", (target, now(), job_id))
            if target == "confirmed":
                self.db.execute("UPDATE records SET status='issued',version=version+1,updated_at=? WHERE id=?", (now(), job["record_id"]))
            self.audit("print." + target, job_id, detail[:500])

    def recover_jobs(self):
        self.authorize()
        with self.transaction():
            rows = self.db.execute("SELECT id FROM jobs WHERE status='prepared'").fetchall()
            for row in rows:
                self.db.execute("UPDATE jobs SET status='uncertain',updated_at=? WHERE id=?", (now(), row["id"]))
                self.audit("print.interrupted", row["id"], "Check physical output before any retry")

    def save_template(self, name, body):
        self.authorize(admin=True)
        from .templates import validate_template
        validate_template(body)
        name = name.strip()
        if not name or len(name) > 80:
            raise DomainError("Template name must contain 1–80 characters.")
        with self.transaction():
            used = self.db.execute("SELECT 1 FROM records WHERE template=? AND status!='draft'", (name,)).fetchone()
            if used:
                raise DomainError("This template is used by approved cards. Save under a new name to create a revision.")
            self.db.execute("INSERT INTO templates VALUES(?,?) ON CONFLICT(name) DO UPDATE SET body=excluded.body", (name, json.dumps(body)))
            self.audit("template.saved", name)

    def templates(self):
        self.authorize()
        return {r["name"]: json.loads(r["body"]) for r in self.db.execute("SELECT * FROM templates ORDER BY name")}

    def backup(self, destination):
        from .fileio import atomic_output
        self.authorize(admin=True)
        destination = Path(destination)
        protected = {"studio.db", "studio.db-wal", "studio.db-shm", "workstation.lock", "application.log"}
        if destination.resolve() in {(self.folder / name).resolve() for name in protected}:
            raise DomainError("Choose a separate backup file.")
        with tempfile.TemporaryDirectory() as temporary:
            backup_db = Path(temporary) / "studio.db"
            with closing(sqlite3.connect(backup_db)) as connection:
                self.db.backup(connection)
            if backup_db.stat().st_size > 2_000_000_000:
                raise DomainError("Database exceeds the 2 GB backup/restore limit.")
            with backup_db.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            manifest = {"format": 1, "created_at": now(), "sha256": digest}
            with atomic_output(destination) as temporary_archive:
                with zipfile.ZipFile(temporary_archive, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(backup_db, "studio.db")
                    archive.writestr("manifest.json", json.dumps(manifest))
        with self.transaction():
            self.audit("backup.created")

    @staticmethod
    def restore(archive_path, folder):
        """Offline recovery into a NEW directory only. Never overwrite a live database."""
        folder = Path(folder)
        if (folder / "studio.db").exists():
            raise DomainError("Restore requires a new data folder; existing data will not be overwritten.")
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            candidate = Path(temporary) / "studio.db"
            with zipfile.ZipFile(archive_path) as archive:
                if len(archive.namelist()) != 2 or set(archive.namelist()) != {"studio.db", "manifest.json"}:
                    raise DomainError("Unexpected backup contents.")
                if archive.getinfo("studio.db").file_size > 2_000_000_000 or archive.getinfo("manifest.json").file_size > 4096:
                    raise DomainError("Backup exceeds supported size.")
                manifest = json.loads(archive.read("manifest.json"))
                with archive.open("studio.db") as source, candidate.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                with candidate.open("rb") as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                if manifest.get("format") != 1 or digest != manifest.get("sha256"):
                    raise DomainError("Backup integrity check failed.")
            with closing(sqlite3.connect(candidate)) as db:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise DomainError("Backup database is damaged.")
                if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise DomainError("Unsupported backup version.")
                db.execute("SELECT id,username,password,role FROM users LIMIT 1")
                db.execute("SELECT id,card_no,full_name,photo,signature,consent,status,version FROM records LIMIT 0")
                db.execute("SELECT id,record_id,snapshot,front,back,status FROM jobs LIMIT 0")
                db.execute("SELECT name,body FROM templates LIMIT 0")
                db.execute("SELECT at,actor,action,target,detail FROM audit LIMIT 0")
                if db.execute("PRAGMA foreign_key_check").fetchone():
                    raise DomainError("Backup contains broken database references.")
            # Exclusive creation closes the overwrite race.
            destination = folder / "studio.db"
            # Remove our own incomplete output if disk-full interrupts recovery.
            # An existing file is never opened, replaced or removed.
            output = destination.open("xb")
            try:
                with output, candidate.open("rb") as source:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
            except Exception:
                destination.unlink(missing_ok=True)
                raise

    def close(self):
        self.db.close()
