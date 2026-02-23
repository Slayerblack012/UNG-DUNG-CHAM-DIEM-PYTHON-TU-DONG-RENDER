"""
DSA AutoGrader — API Endpoints.

Định nghĩa tất cả HTTP routes:
  • POST /grade              — Nộp bài & chấm điểm (async background job)
  • GET  /api/job/{job_id}   — Polling trạng thái job
  • GET  /api/scores/...     — Truy vấn dữ liệu
  • GET  /api/stats          — Thống kê
  • GET  / , /results        — Serve frontend pages
"""

import asyncio
import time
import uuid
import logging
from typing import Any, Dict, List, Optional

import httpx

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi_utils.tasks import repeat_every

from app.core.config import BASE_DIR, MAX_CONCURRENT_AI_CALLS, JOB_TTL_SECONDS
from app.services.grader import AIGrader
from app.services.file_processing import FileProcessingService
from app.models.database import db

import os

logger = logging.getLogger("dsa.endpoints")

# ═══════════════════════════════════════════
#  Router & Services
# ═══════════════════════════════════════════
router = APIRouter()
grader = AIGrader()
ai_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AI_CALLS)

# Job store — in-memory (production nên dùng Redis)
_job_store: Dict[str, Dict[str, Any]] = {}


# ═══════════════════════════════════════════
#  Job Management
# ═══════════════════════════════════════════

def cleanup_expired_jobs() -> int:
    """Xóa các job đã hết hạn TTL. Trả về số job đã xóa."""
    now = time.time()
    expired = [
        jid for jid, data in _job_store.items()
        if now - data.get("created_at", 0) > JOB_TTL_SECONDS
    ]
    for jid in expired:
        del _job_store[jid]
    if expired:
        logger.info("Cleaned up %d expired jobs.", len(expired))
    return len(expired)

@router.on_event("startup")
@repeat_every(seconds=3600)  # Chạy 1 giờ / lần
def periodic_job_cleanup():
    """Tự động dọn rác bộ nhớ Job Store định kỳ để tránh rò rỉ RAM."""
    cleanup_expired_jobs()


# ═══════════════════════════════════════════
#  Webhook: Gửi kết quả ra hệ thống ngoài
# ═══════════════════════════════════════════

async def _send_webhook(url: str, job_id: str, data: Dict) -> None:
    """
    POST kết quả chấm điểm sang hệ thống bên ngoài (Dashboard, LMS, ...).
    Gửi tối đa 3 lần nếu thất bại.
    """
    payload = {
        "event": "grading_completed",
        "job_id": job_id,
        "results": data.get("results", []),
        "summary": data.get("summary", {}),
    }

    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            logger.info("Webhook sent to '%s' (attempt %d)", url, attempt)
            return
        except Exception as exc:
            logger.warning("Webhook attempt %d failed: %s", attempt, exc)
            await asyncio.sleep(2 ** attempt)  # Exponential Backoff (2s, 4s, 8s)

    logger.error("Webhook to '%s' failed after 3 attempts.", url)


# ═══════════════════════════════════════════
#  Background Grading Pipeline
# ═══════════════════════════════════════════

async def _grade_single_file(code: str, filename: str, topic: str) -> Dict[str, Any]:
    """Chấm điểm một file, giới hạn bởi semaphore."""
    async with ai_semaphore:
        return await grader.grade_auto(code, filename, topic=topic)


async def _run_grading_job(
    job_id: str,
    files_data: List[tuple],
    topic: str,
    student_name: str,
    assignment_code: str | None,
    callback_url: str | None = None,
) -> None:
    """
    Background job: Chấm điểm tất cả files → kiểm đạo văn → lưu DB.
    """
    start_time = time.time()

    try:
        _job_store[job_id]["status"] = "processing"

        # 1. Chấm điểm song song tất cả files
        tasks = [
            _grade_single_file(content, fname, topic)
            for fname, content in files_data
        ]

        if not tasks:
            _job_store[job_id]["status"] = "failed"
            _job_store[job_id]["error"] = "Không tìm thấy file hợp lệ."
            return

        results = await asyncio.gather(*tasks)

        # 2. Kiểm tra đạo văn giữa các bài nộp
        results = grader.check_plagiarism(list(results))

        # 3. Gắn thông tin sinh viên vào filename
        for result in results:
            if " | " not in result.get("filename", ""):
                result["filename"] = f"{student_name} | {result['filename']}"

        # 4. Lưu vào Database
        saved_count = 0
        try:
            saved_ids = db.save_batch_results(results, assignment_code=assignment_code)
            saved_count = len(saved_ids)
        except Exception as exc:
            logger.error("DB batch save failed: %s", exc)

        # 5. Hoàn tất job
        elapsed = time.time() - start_time
        scores = [r.get("total_score") for r in results if r.get("total_score") is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else None

        _job_store[job_id].update({
            "status": "completed",
            "results": results,
            "summary": {
                "total_files": len(results),
                "avg_score": avg_score,
                "total_time": f"{elapsed:.1f}s",
                "saved_to_db": saved_count,
            },
        })

        logger.info(
            "Job %s completed: %d files, avg=%.1f, time=%.1fs",
            job_id[:8], len(results), avg_score, elapsed,
        )

        # 6. Webhook: Gửi kết quả sang hệ thống bên ngoài (nếu có)
        if callback_url:
            await _send_webhook(callback_url, job_id, _job_store[job_id])

    except Exception as exc:
        logger.error("Job %s failed: %s", job_id[:8], exc)
        _job_store[job_id]["status"] = "failed"
        _job_store[job_id]["error"] = str(exc)


# ═══════════════════════════════════════════
#  ENDPOINTS: Grading
# ═══════════════════════════════════════════

@router.post("/grade")
async def grade_submissions(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    topic: str = Form(None),
    student_name: str = Form("An danh"),
    assignment_code: str = Form(None),
    callback_url: str = Form(None),
) -> Dict[str, Any]:
    """
    API chấm điểm (Async Background Job).
    Trả về Job ID ngay lập tức → client polling qua /api/job/{job_id}.
    """
    # Cleanup jobs cũ trước khi tạo mới
    cleanup_expired_jobs()

    # 1. Giải nén và thu thập code
    all_files: List[tuple] = []
    for file in files:
        extracted = await FileProcessingService.process_upload(file)
        all_files.extend(extracted)

    if not all_files:
        return JSONResponse(
            {"error": "Không tìm thấy file Python hợp lệ trong bài nộp."},
            status_code=400,
        )

    # 2. Tạo background job
    job_id = str(uuid.uuid4())
    _job_store[job_id] = {
        "status": "pending",
        "student": student_name,
        "created_at": time.time(),
    }

    background_tasks.add_task(
        _run_grading_job,
        job_id,
        all_files,
        topic or "",
        student_name,
        assignment_code,
        callback_url,
    )

    return {
        "job_id": job_id,
        "status": "accepted",
        "message": f"Dang xu ly {len(all_files)} file...",
        "callback_url": callback_url,
    }


@router.get("/api/job/{job_id}")
async def get_job_status(job_id: str) -> Any:
    """Polling trạng thái job chấm điểm."""
    job = _job_store.get(job_id)
    if not job:
        return JSONResponse(
            {"error": "Không tìm thấy phiên chấm điểm."},
            status_code=404,
        )
    return job


# ═══════════════════════════════════════════
#  ENDPOINTS: Reporting & Stats
# ═══════════════════════════════════════════

@router.get("/api/scores/student/{student_id}")
async def get_student_scores(student_id: str) -> Dict[str, Any]:
    """Lấy lịch sử điểm của một sinh viên."""
    scores = db.get_student_scores(student_id)
    return {"student_id": student_id, "submissions": scores, "total": len(scores)}


@router.get("/api/scores/assignment/{assignment_code}")
async def get_assignment_scores(assignment_code: str) -> Dict[str, Any]:
    """Lấy bảng điểm theo mã bài tập."""
    scores = db.get_assignment_scores(assignment_code)
    return {"assignment_code": assignment_code, "submissions": scores, "total": len(scores)}


@router.get("/api/stats")
async def get_statistics(assignment_code: str = Query(None)) -> Dict[str, Any]:
    """Thống kê phân phối điểm số."""
    return db.get_stats(assignment_code)


# ═══════════════════════════════════════════
#  ENDPOINTS: Frontend Pages
# ═══════════════════════════════════════════

@router.get("/", response_class=FileResponse)
async def home_page() -> str:
    """Trang nộp bài."""
    return os.path.join(BASE_DIR, "static", "index.html")


@router.get("/results", response_class=FileResponse)
async def results_page() -> str:
    """Trang kết quả chấm điểm."""
    return os.path.join(BASE_DIR, "static", "results.html")
