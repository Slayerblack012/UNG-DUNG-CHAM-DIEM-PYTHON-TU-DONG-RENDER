"""
DSA AutoGrader — File Processing Service.

Xử lý file upload: lưu tạm vào đĩa, giải nén, chuẩn hóa encoding.
Hỗ trợ: .py, .zip, .rar
"""

import os
import shutil
import asyncio
import zipfile
import tempfile
import logging
from typing import List, Tuple

from fastapi import UploadFile

logger = logging.getLogger("dsa.file_processing")

# Optional RAR support
try:
    import rarfile
except ImportError:
    rarfile = None

# Upload chunk size: 1 MB
_CHUNK_SIZE = 1024 * 1024

# Encoding fallback chain
_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "iso-8859-1")


class FileProcessingService:
    """
    Service xử lý file upload.
    Lưu tạm vào đĩa → giải nén (nếu cần) → trả về list (filename, code).
    """

    @staticmethod
    async def process_upload(file: UploadFile) -> List[Tuple[str, str]]:
        """
        Xử lý một file upload.

        Returns:
            List[Tuple[str, str]]: Danh sách (tên_file, nội_dung_code).
        """
        temp_dir = tempfile.mkdtemp(prefix="dsa_upload_")
        results: List[Tuple[str, str]] = []

        try:
            # 1. Lưu file upload vào đĩa (chunk-based để tiết kiệm RAM)
            saved_path = os.path.join(temp_dir, file.filename)
            with open(saved_path, "wb") as buffer:
                while True:
                    chunk = await file.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    buffer.write(chunk)

            filename_lower = file.filename.lower()
            loop = asyncio.get_running_loop()

            # 2. Xử lý theo loại file
            if filename_lower.endswith(".zip"):
                results = await loop.run_in_executor(
                    None, _extract_zip, saved_path, file.filename
                )
            elif filename_lower.endswith(".rar"):
                if rarfile is None:
                    logger.warning("RAR support not installed. Skipping %s.", file.filename)
                else:
                    results = await loop.run_in_executor(
                        None, _extract_rar, saved_path, file.filename
                    )
            elif filename_lower.endswith(".py"):
                with open(saved_path, "rb") as f:
                    text = _decode_bytes(f.read())
                    if text.strip():
                        results = [(file.filename, text)]

            return results

        except Exception as exc:
            logger.error("Xử lý file thất bại '%s': %s", file.filename, exc)
            return []

        finally:
            # 3. Dọn dẹp thư mục tạm
            try:
                shutil.rmtree(temp_dir)
            except OSError as exc:
                logger.warning("Không thể xóa thư mục tạm: %s", exc)


# ═══════════════════════════════════════════
#  Private Extraction Functions
# ═══════════════════════════════════════════

def _extract_zip(file_path: str, parent_name: str) -> List[Tuple[str, str]]:
    """Giải nén ZIP, trả về list (filename, code) cho các file .py."""
    results: List[Tuple[str, str]] = []
    try:
        with zipfile.ZipFile(file_path) as zf:
            for member in zf.namelist():
                if _is_junk(member) or not member.lower().endswith(".py"):
                    continue
                try:
                    with zf.open(member) as f:
                        text = _decode_bytes(f.read())
                        if text.strip():
                            clean_name = f"{parent_name}/{member.split('/')[-1]}"
                            results.append((clean_name, text))
                except Exception as exc:
                    logger.warning("Lỗi đọc '%s' trong ZIP: %s", member, exc)
    except zipfile.BadZipFile as exc:
        logger.error("ZIP hỏng '%s': %s", parent_name, exc)
    return results


def _extract_rar(file_path: str, parent_name: str) -> List[Tuple[str, str]]:
    """Giải nén RAR, trả về list (filename, code) cho các file .py."""
    results: List[Tuple[str, str]] = []
    if rarfile is None:
        return results

    try:
        with rarfile.RarFile(file_path) as rf:
            for member in rf.namelist():
                if _is_junk(member) or not member.lower().endswith(".py"):
                    continue
                try:
                    raw = rf.read(member)
                    text = _decode_bytes(raw)
                    if text.strip():
                        clean_name = f"{parent_name}/{member.split('/')[-1]}"
                        results.append((clean_name, text))
                except Exception as exc:
                    logger.warning("Lỗi đọc '%s' trong RAR: %s", member, exc)
    except Exception as exc:
        logger.error("RAR lỗi '%s': %s", parent_name, exc)
    return results


# ═══════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════

def _is_junk(path: str) -> bool:
    """Kiểm tra file rác (file ẩn, __pycache__, macOS metadata, etc.)."""
    name = path.replace("\\", "/").split("/")[-1]
    return (
        name.startswith(".")
        or name.startswith("__")
        or name.lower() == "thumbs.db"
        or "__MACOSX" in path
    )


def _decode_bytes(data: bytes) -> str:
    """Giải mã bytes → string với fallback encoding chain."""
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")
