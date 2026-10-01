import importlib.util
from importlib.metadata import distribution
from pathlib import Path


def test_notices_preserve_raw_wheel_metadata(tmp_path):
    path=Path(__file__).resolve().parents[1]/"packaging"/"collect_notices.py"
    spec=importlib.util.spec_from_file_location("collect_notices",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.collect_notices(tmp_path,packages=("PySide6","shiboken6"))
    assert (tmp_path/"PySide6"/"METADATA.txt").read_text(encoding="utf-8")==distribution("PySide6").read_text("METADATA")
    assert (tmp_path/"shiboken6"/"METADATA.txt").exists()
