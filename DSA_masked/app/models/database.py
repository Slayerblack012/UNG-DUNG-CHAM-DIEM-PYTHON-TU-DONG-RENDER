"""
DSA AutoGrader — Data Persistence Layer (JSON File Storage).

Lưu kết quả chấm điểm dưới dạng file JSON trên ổ cứng.
  - Mỗi phiên chấm = 1 file JSON (dễ đọc, dễ debug)
  - Tự động tạo thư mục theo ngày: data/scores/2026-02-22/
  - Dữ liệu tồn tại vĩnh viễn khi restart server
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.core.config import BASE_DIR

logger = logging.getLogger("dsa.database")

# Thư mục gốc lưu điểm
SCORES_DIR = os.path.join(BASE_DIR, "data", "scores")


class GradeDatabase:
    """
    JSON File-based Database.
    Lưu kết quả chấm điểm vào file JSON, tổ chức theo ngày.

    Cấu trúc thư mục:
        data/scores/
        ├── 2026-02-22/
        │   ├── 001_NguyenVanA_sorting.json
        │   ├── 002_TranVanB_searching.json
        │   └── ...
        ├── 2026-02-23/
        │   └── ...
        └── _index.json   (danh sách tổng hợp, load nhanh)
    """

    def __init__(self) -> None:
        self._counter: int = 0

    def initialize(self) -> None:
        """Khởi tạo thư mục lưu trữ và đếm records hiện có."""
        os.makedirs(SCORES_DIR, exist_ok=True)
        self._counter = self._count_existing_records()
        logger.info(
            "JSON Storage ready at '%s' — %d records found.",
            SCORES_DIR, self._counter,
        )

    # ═══════════════════════════════════════════
    #  Write Operations
    # ═══════════════════════════════════════════

    def save_result(
        self,
        result: Dict,
        student_id_input: Optional[str] = None,
        assignment_code: Optional[str] = None,
    ) -> Optional[int]:
        """Lưu một kết quả chấm điểm thành file JSON."""
        try:
            self._counter += 1
            record_id = self._counter
            now = datetime.now()

            # Parse student info
            filename = result.get("filename", "unknown")
            s_id, s_name = self._parse_student_info(filename, student_id_input)

            # Build record
            record = {
                "id": record_id,
                "student_id": s_id,
                "student_name": s_name,
                "assignment_code": assignment_code,
                "filename": filename,
                "topic": result.get("topic"),
                "total_score": result.get("total_score", 0),
                "breakdown": result.get("breakdown", {}),
                "algorithms": result.get("algorithms"),
                "complexity": result.get("complexity", 0),
                "status": result.get("status", "PENDING"),
                "reasoning": result.get("reasoning", ""),
                "improvement": result.get("improvement", ""),
                "notes": result.get("notes", []),
                "ai_scored": result.get("ai_scored", False),
                "runtime": result.get("runtime"),
                "submitted_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Tạo thư mục theo ngày
            date_dir = os.path.join(SCORES_DIR, now.strftime("%Y-%m-%d"))
            os.makedirs(date_dir, exist_ok=True)

            # Tên file: 001_NguyenVanA_sorting.json
            safe_name = s_name.replace(" ", "").replace("/", "_")[:20]
            topic_tag = (assignment_code or result.get("topic") or "general")[:15]
            json_filename = f"{record_id:03d}_{safe_name}_{topic_tag}.json"
            json_path = os.path.join(date_dir, json_filename)

            # Ghi file JSON (indent=2 cho dễ đọc)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)

            logger.info("Saved #%d → %s", record_id, json_path)
            return record_id

        except Exception as exc:
            logger.error("Save failed: %s", exc)
            return None

    def save_batch_results(
        self,
        results: List[Dict],
        assignment_code: Optional[str] = None,
    ) -> List[int]:
        """Lưu nhiều kết quả. Trả về danh sách ID đã lưu."""
        saved_ids: List[int] = []
        for result in results:
            record_id = self.save_result(result, assignment_code=assignment_code)
            if record_id is not None:
                saved_ids.append(record_id)
        return saved_ids

    # ═══════════════════════════════════════════
    #  Read Operations
    # ═══════════════════════════════════════════

    def get_student_scores(self, student_id: str) -> List[Dict]:
        """Lấy tất cả kết quả của một sinh viên."""
        all_records = self._load_all_records()
        return [r for r in all_records if r.get("student_id") == student_id]

    def get_assignment_scores(self, assignment_code: str) -> List[Dict]:
        """Lấy bảng điểm theo mã bài tập, sắp xếp điểm giảm dần."""
        all_records = self._load_all_records()
        filtered = [r for r in all_records if r.get("assignment_code") == assignment_code]
        return sorted(filtered, key=lambda x: x.get("total_score", 0), reverse=True)

    def get_stats(self, assignment_code: Optional[str] = None) -> Dict:
        """Thống kê tổng hợp."""
        all_records = self._load_all_records()
        if assignment_code:
            all_records = [r for r in all_records if r.get("assignment_code") == assignment_code]

        if not all_records:
            return {
                "total_submissions": 0, "avg_score": 0,
                "max_score": 0, "min_score": 0,
                "passed": 0, "failed": 0, "flagged": 0,
            }

        scores = [r.get("total_score", 0) for r in all_records]
        return {
            "total_submissions": len(all_records),
            "avg_score": round(sum(scores) / len(scores), 1),
            "max_score": max(scores),
            "min_score": min(scores),
            "passed": sum(1 for r in all_records if r.get("status") == "PASS"),
            "failed": sum(1 for r in all_records if r.get("status") == "FAIL"),
            "flagged": sum(1 for r in all_records if r.get("status") == "FLAG"),
        }

    # ═══════════════════════════════════════════
    #  Internal Helpers
    # ═══════════════════════════════════════════

    def _load_all_records(self) -> List[Dict]:
        """Đọc tất cả file JSON trong thư mục scores."""
        records: List[Dict] = []
        if not os.path.exists(SCORES_DIR):
            return records

        for date_folder in sorted(os.listdir(SCORES_DIR)):
            folder_path = os.path.join(SCORES_DIR, date_folder)
            if not os.path.isdir(folder_path):
                continue
            for json_file in sorted(os.listdir(folder_path)):
                if not json_file.endswith(".json"):
                    continue
                try:
                    file_path = os.path.join(folder_path, json_file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        records.append(json.load(f))
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning("Skip corrupt file '%s': %s", json_file, exc)

        return records

    def _count_existing_records(self) -> int:
        """Đếm số record hiện có để tiếp tục đánh ID."""
        count = 0
        if not os.path.exists(SCORES_DIR):
            return 0
        for date_folder in os.listdir(SCORES_DIR):
            folder_path = os.path.join(SCORES_DIR, date_folder)
            if os.path.isdir(folder_path):
                count += sum(1 for f in os.listdir(folder_path) if f.endswith(".json"))
        return count

    @staticmethod
    def _parse_student_info(filename: str, provided_id: Optional[str]) -> tuple:
        """
        Tách thông tin sinh viên từ filename.
        Format: "MSSV - Ho Ten | filename.py"  hoặc  "Ho Ten | filename.py"
        """
        s_id = provided_id or "anonymous"
        s_name = "Unknown"

        if " | " in filename:
            try:
                info_part = filename.split(" | ", 1)[0]
                if " - " in info_part:
                    s_id, s_name = info_part.split(" - ", 1)
                else:
                    s_name = info_part
            except (ValueError, IndexError):
                pass

        return s_id.strip(), s_name.strip()


# ── Singleton Instance ─────────────────────
db = GradeDatabase()
