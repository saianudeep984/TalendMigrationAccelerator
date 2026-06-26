import zipfile

import pytest

from app.utils.zip_extractor import safe_extract


def _write_zip(path, member_name):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member_name, "payload")


def test_safe_extract_rejects_parent_directory_member(tmp_path):
    zip_path = tmp_path / "bad_parent.zip"
    _write_zip(zip_path, "../escape.txt")

    with pytest.raises(ValueError):
        safe_extract(zip_path, tmp_path / "out")


def test_safe_extract_rejects_absolute_member(tmp_path):
    zip_path = tmp_path / "bad_absolute.zip"
    _write_zip(zip_path, "/escape.txt")

    with pytest.raises(ValueError):
        safe_extract(zip_path, tmp_path / "out")
