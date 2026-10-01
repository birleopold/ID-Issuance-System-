"""Bounded CSV parsing and read-only review before transactional draft import."""
import csv
from pathlib import Path

from .core import DomainError

COLUMNS = ("card_no", "full_name", "department", "title", "expires")
REQUIRED = {"card_no", "full_name", "expires"}


def read_csv(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise DomainError("CSV exceeds 2 MB. Split it into smaller batches.")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)):
                raise DomainError("CSV has duplicate column headers.")
            if not REQUIRED.issubset(headers) or not set(headers).issubset(COLUMNS):
                raise DomainError("CSV requires card_no, full_name, expires. Optional columns: department, title. Other columns are not accepted.")
            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise DomainError(f"CSV row near line {reader.line_num} has missing or extra columns.")
                rows.append({key: row.get(key, "").strip() for key in COLUMNS})
                if len(rows) > 1000:
                    raise DomainError("Import up to 1,000 rows at a time.")
            if not rows:
                raise DomainError("The CSV contains no cardholders.")
            return rows
    except (UnicodeError, csv.Error) as exc:
        raise DomainError("Cannot read the CSV. Save it as UTF-8 CSV with comma separators.") from exc


def review_rows(store, rows, template):
    store.authorize(admin=True)
    errors = []
    seen = set()
    for row in rows:
        messages = []
        try:
            store.validate_record({**row, "template": template, "consent": False})
        except DomainError as exc:
            messages.append(str(exc))
        number = row["card_no"].strip()
        folded = number.casefold()
        if folded in seen:
            messages.append("Duplicate card number within this file")
        seen.add(folded)
        if store.db.execute("SELECT 1 FROM records WHERE card_no=?", (number,)).fetchone():
            messages.append("Card number already exists")
        errors.append("; ".join(messages))
    return errors
