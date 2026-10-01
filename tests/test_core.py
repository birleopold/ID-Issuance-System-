import copy
import json
import sqlite3
import zipfile
import pytest

from idstudio.core import DomainError,Store
from idstudio.templates import default_templates,validate_template


def test_first_account_must_be_admin(tmp_path):
    store=Store(tmp_path)
    with pytest.raises(DomainError):
        store.create_user("operator","password long enough","operator")
    store.close()


def test_wrong_password_rate_limit_persists(store):
    for _ in range(5):
        with pytest.raises(DomainError):
            store.login("admin","incorrect")
    with pytest.raises(DomainError,match="locked"):
        store.login("admin","correct horse battery")
    assert store.db.execute("SELECT failures FROM users").fetchone()[0]==5


def test_account_creation_requires_admin(store):
    store.create_user("operator","operator passphrase")
    store.login("operator","operator passphrase")
    with pytest.raises(DomainError):
        store.create_user("attacker","another passphrase","admin")


def test_duplicate_card_case_insensitive(store,values):
    store.save_record(values)
    with pytest.raises(DomainError,match="already in use"):
        store.save_record({**values,"card_no":"emp-001"})
    assert len(store.records())==1


def test_lost_update_rejected(store,values):
    record=store.save_record(values)
    store.save_record({**values,"full_name":"Revised Name"},record,1)
    with pytest.raises(DomainError,match="changed"):
        store.save_record(values,record,1)
    assert store.get_record(record)["full_name"]=="Revised Name"


@pytest.mark.parametrize("patch",[{"photo":None},{"signature":None},{"consent":False},{"expires":"2000-01-01"}])
def test_approval_requires_complete_valid_record(store,values,patch):
    record=store.save_record({**values,**patch})
    with pytest.raises(DomainError):
        store.transition(record,"approved")
    assert store.get_record(record)["status"]=="draft"


def test_operator_cannot_approve_or_revoke(store,values):
    record=store.save_record(values)
    store.create_user("operator","operator passphrase")
    store.login("operator","operator passphrase")
    with pytest.raises(DomainError):
        store.transition(record,"approved")


def test_approved_record_and_template_are_immutable(store,values):
    record=store.save_record(values)
    store.transition(record,"approved")
    with pytest.raises(DomainError,match="Only drafts"):
        store.save_record(values,record,2)
    with pytest.raises(DomainError,match="revision"):
        store.save_template(values["template"],default_templates()[values["template"]])


def test_full_issuance_and_reprint_lifecycle(store,values):
    record=store.save_record(values)
    store.transition(record,"approved")
    job=store.prepare_job(record,2,b"front",b"back","printer")
    with pytest.raises(DomainError,match="existing print"):
        store.prepare_job(record,2,b"front",b"back","printer")
    with pytest.raises(DomainError,match="pending print"):
        store.transition(record,"draft","correction")
    store.finish_job(job,"submitted")
    assert store.get_record(record)["status"]=="approved"
    store.finish_job(job,"confirmed","Inspected both sides")
    assert store.get_record(record)["status"]=="issued"
    with pytest.raises(DomainError,match="reason"):
        store.prepare_job(record,3,b"front",b"back","printer")
    repeat=store.prepare_job(record,3,b"front",b"back","printer","Lost original")
    store.finish_job(repeat,"uncertain")
    store.finish_job(repeat,"failed","No physical output; queue cleared")
    store.transition(record,"revoked","Employee left")
    with pytest.raises(DomainError):
        store.prepare_job(record,4,b"front",b"back","printer","replacement")


def test_interrupted_job_is_uncertain_and_never_auto_retried(store,values):
    record=store.save_record(values)
    store.transition(record,"approved")
    job=store.prepare_job(record,2,b"front",b"back","printer")
    store.recover_jobs()
    assert store.db.execute("SELECT status FROM jobs WHERE id=?",(job,)).fetchone()[0]=="uncertain"
    with pytest.raises(DomainError):
        store.prepare_job(record,2,b"front",b"back","printer")


def test_audit_cannot_be_edited_via_sql(store):
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute("DELETE FROM audit")
    store.db.rollback()


def test_backup_restore_includes_media_and_templates(store,values,tmp_path):
    record=store.save_record(values)
    path=tmp_path/"backup.zip"
    store.backup(path)
    folder=tmp_path/"recovered"
    Store.restore(path,folder)
    recovered=Store(folder)
    recovered.login("admin","correct horse battery")
    assert recovered.get_record(record)["signature"]==values["signature"]
    assert recovered.templates()==store.templates()
    recovered.close()
    with pytest.raises(DomainError,match="new data folder"):
        Store.restore(path,folder)


def test_tampered_backup_rejected(store,tmp_path):
    path=tmp_path/"bad.zip"
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr("studio.db",b"bad data")
        archive.writestr("manifest.json",json.dumps({"format":1,"sha256":"incorrect"}))
    with pytest.raises(DomainError,match="integrity"):
        Store.restore(path,tmp_path/"restore")


@pytest.mark.parametrize("value",[float("nan"),float("inf"),-1,1000])
def test_template_bounds_and_nonfinite_values(value):
    body=copy.deepcopy(default_templates()["Corporate / Ocean"])
    body["front"][0]["x"]=value
    with pytest.raises(DomainError):
        validate_template(body)


def test_disabled_account_cannot_use_old_session(store):
    store.create_user("operator","operator passphrase")
    store.login("operator","operator passphrase")
    store.db.execute("UPDATE users SET active=0 WHERE username='operator'")
    store.db.commit()
    with pytest.raises(DomainError):
        store.records()


def test_password_change_invalidates_old_password(store):
    store.change_password("correct horse battery","new long passphrase")
    with pytest.raises(DomainError):
        store.login("admin","correct horse battery")
    store.login("admin","new long passphrase")


def test_draft_cannot_be_printed(store,values):
    record=store.save_record(values)
    with pytest.raises(DomainError,match="approve"):
        store.prepare_job(record,1,b"front",b"back","printer")


def test_print_resolution_is_not_repeatable(store,values):
    record=store.save_record(values)
    store.transition(record,"approved")
    job=store.prepare_job(record,2,b"front",b"back","printer")
    store.finish_job(job,"submitted")
    store.finish_job(job,"confirmed","Checked")
    with pytest.raises(DomainError):
        store.finish_job(job,"confirmed","Checked again")
