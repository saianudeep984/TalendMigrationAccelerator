import zipfile
import os
from pathlib import Path, PurePosixPath


def _is_unsafe_member(member_name):
    normalized = member_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    windows_drive = len(normalized) >= 2 and normalized[1] == ":"
    return path.is_absolute() or windows_drive or ".." in path.parts


def safe_extract(zip_path, dest):
    dest_path = Path(dest).resolve()
    dest_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for member in zip_ref.infolist():
            if _is_unsafe_member(member.filename):
                raise ValueError(f"Unsafe ZIP member path: {member.filename}")

            target_path = (dest_path / member.filename).resolve()
            if dest_path != target_path and dest_path not in target_path.parents:
                raise ValueError(f"Unsafe ZIP member path: {member.filename}")

        zip_ref.extractall(dest_path)

    return str(dest_path)


def extract_zip(zip_path, extract_to="temp_repository"):

    if not os.path.exists(extract_to):
        os.makedirs(extract_to)

    safe_extract(zip_path, extract_to)

    return extract_to
