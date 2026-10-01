import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from idstudio.core import Store
from idstudio.templates import default_templates


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path):
    service=Store(tmp_path / "data")
    service.create_user("admin","correct horse battery","admin")
    service.login("admin","correct horse battery")
    for name,body in default_templates().items():
        service.save_template(name,body)
    yield service
    service.close()


@pytest.fixture
def values():
    return dict(card_no="EMP-001",full_name="Alex Morgan",department="Operations",title="Manager",
                expires="2099-12-31",template="Corporate / Ocean",photo=b"photo",signature=b"signature",consent=True)
