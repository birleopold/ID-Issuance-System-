import json
from datetime import datetime, timedelta, timezone
import zipfile

import pytest

from idstudio.core import DomainError, Store
from idstudio.fileio import atomic_output
from idstudio.importing import read_csv, review_rows
from idstudio.widgets import CSVImportDialog


def test_csv_import_review_then_drafts_only(store, tmp_path):
    path = tmp_path / "batch.csv"
    path.write_text('\ufeffcard_no,full_name,expires,department\nEMP-100,"Namutebi, Grace",2099-12-31,HR\nEMP-101,Alex Morgan,2099-12-31,IT\n', encoding="utf-8")
    rows = read_csv(path)
    assert review_rows(store, rows, "Corporate / Ocean") == ["", ""]
    assert store.record_count() == 0
    ids = store.import_drafts(rows, "Corporate / Ocean")
    assert len(ids) == 2
    record = store.get_record(ids[0])
    assert record["full_name"] == "Namutebi, Grace"
    assert record["status"] == "draft"
    assert record["photo"] is None and record["signature"] is None and not record["consent"]
    with pytest.raises(DomainError):
        store.transition(ids[0], "approved")


def test_csv_batch_rolls_back_on_late_duplicate_and_audit(store, values):
    existing = store.save_record(values)
    count = store.db.execute("SELECT count(*) FROM audit").fetchone()[0]
    with pytest.raises(DomainError, match="Nothing was imported"):
        store.import_drafts([{**values, "card_no": "NEW"}, values], "Corporate / Ocean")
    assert store.record_count() == 1
    assert store.get_record(existing)["full_name"] == values["full_name"]
    assert store.db.execute("SELECT count(*) FROM audit").fetchone()[0] == count


def test_review_revalidates_duplicate_at_commit(store, values):
    assert review_rows(store, [values], "Corporate / Ocean") == [""]
    store.save_record(values)
    with pytest.raises(DomainError):
        store.import_drafts([values], "Corporate / Ocean")
    assert store.record_count() == 1


def test_import_never_accepts_approval_or_media_fields(store, values):
    ids = store.import_drafts([{**values, "status": "issued", "id": "injected"}], "Corporate / Ocean")
    record = store.get_record(ids[0])
    assert record["status"] == "draft" and record["photo"] is None
    assert record["id"] != "injected" and record["consent"] == 0


def test_operator_cannot_bulk_import_or_export(store, values):
    store.create_user("operator", "operator passphrase")
    store.login("operator", "operator passphrase")
    with pytest.raises(DomainError):
        store.import_drafts([values], "Corporate / Ocean")
    with pytest.raises(DomainError):
        store.export_records()


@pytest.mark.parametrize("content", [
    "card_no,full_name,expires,status\na,Name,2099-01-01,issued\n",
    "card_no,card_no,expires\na,b,2099-01-01\n",
    "card_no,full_name,expires\na,Name\n",
    "card_no,full_name,expires\na,Name,2099-01-01,extra\n",
    "card_no,full_name,expires\n",
])
def test_invalid_csv_is_rejected(tmp_path, content):
    path = tmp_path / "bad.csv"
    path.write_text(content)
    with pytest.raises(DomainError):
        read_csv(path)


def test_duplicate_preview_disables_import(app, store, values):
    rows = [values, {**values, "card_no": "emp-001"}]
    dialog = CSVImportDialog(store, rows)
    assert not dialog.import_button.isEnabled()
    assert "Duplicate" in dialog.table.item(1, 5).text()
    dialog.reject()
    assert store.record_count() == 0


def test_pagination_and_export_reach_beyond_1000(store, values):
    rows = [{**values, "card_no": f"EMP-{i:05}"} for i in range(1000)]
    store.import_drafts(rows, "Corporate / Ocean")
    store.import_drafts([{**values, "card_no": "EMP-10000"}], "Corporate / Ocean")
    ids = []
    for offset in range(0, 1100, 100):
        ids.extend(row["id"] for row in store.records(limit=100, offset=offset))
    assert len(ids) == len(set(ids)) == 1001
    assert store.record_count() == 1001
    assert len(list(store.export_records())) == 1001


def test_expired_filter_and_search_agree(store, values):
    store.save_record({**values, "expires": "2000-01-01"})
    store.save_record({**values, "card_no": "EMP-002"})
    assert store.record_count(status="expired") == 1
    assert len(list(store.export_records(status="expired"))) == 1
    assert len(store.records(search="Morgan", status="expired")) == 1
    assert store.record_count(search="unmatched", status="expired") == 0


def test_backup_failure_preserves_previous_archive(store, tmp_path, monkeypatch):
    destination = tmp_path / "backup.zip"
    store.backup(destination)
    before = destination.read_bytes()
    def fail(*args, **kwargs):
        raise OSError("Simulated full disk")
    monkeypatch.setattr(zipfile.ZipFile, "write", fail)
    with pytest.raises(OSError):
        store.backup(destination)
    assert destination.read_bytes() == before
    assert not list(tmp_path.glob(".credential-*.tmp"))


@pytest.mark.parametrize("name", ["studio.db", "studio.db-wal", "studio.db-shm", "workstation.lock"])
def test_backup_cannot_overwrite_workspace_files(store, name):
    with pytest.raises(DomainError):
        store.backup(store.folder / name)


def test_atomic_export_preserves_existing_file_on_failure(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text("original")
    with pytest.raises(OSError):
        with atomic_output(path) as output:
            output.write_text("partial")
            raise OSError("interrupted")
    assert path.read_text() == "original"
    with atomic_output(path) as output:
        output.write_text("complete")
    assert path.read_text() == "complete"


def test_print_snapshot_records_requested_sides(store, values):
    record = store.save_record(values)
    store.transition(record, "approved")
    job = store.prepare_job(record, 2, b"front", b"back", "Printer", sides="back")
    snapshot = json.loads(store.db.execute("SELECT snapshot FROM jobs WHERE id=?", (job,)).fetchone()[0])
    assert snapshot["sides"] == "back"


def test_expired_lockout_starts_new_attempt_window(store):
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    store.db.execute("UPDATE users SET failures=5,locked_until=?", (expired,))
    store.db.commit()
    with pytest.raises(DomainError):
        store.login("admin", "incorrect")
    row = store.db.execute("SELECT failures,locked_until FROM users").fetchone()
    assert row["failures"] == 1 and row["locked_until"] is None
    store.login("admin", "correct horse battery")


@pytest.mark.parametrize("expiry", ["20991231", "2099-W01-1", "2099-02-30"])
def test_import_review_rejects_noncanonical_dates(store, values, expiry):
    errors = review_rows(store, [{**values, "expires": expiry}], "Corporate / Ocean")
    assert "YYYY-MM-DD" in errors[0]


def test_desktop_pager_and_filter(app, store, values):
    from idstudio.app import MainWindow
    store.import_drafts([{**values, "card_no": f"C-{i}"} for i in range(101)], "Corporate / Ocean")
    window = MainWindow(store)
    window.navigate(1)
    assert window.records_table.rowCount() == 100
    assert window.next_page.isEnabled() and not window.previous_page.isEnabled()
    window.move_record_page(1)
    assert window.records_table.rowCount() == 1
    assert window.previous_page.isEnabled() and not window.next_page.isEnabled()
    window.search.setText("does not exist")
    assert window.record_offset == 0 and window.records_table.rowCount() == 0
    assert "0 matches" in window.record_count.text()
    window.idle_timer.stop()
    window.close()
