"""
DSA AutoGrader — Centralized Configuration Module.
Quản lý tập trung toàn bộ biến môi trường và hằng số ứng dụng.
"""

import os

# ── Load .env (optional, dùng cho local development) ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ═══════════════════════════════════════════
#  API Keys & External Services
# ═══════════════════════════════════════════
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
QUESTION_BANK_API_URL: str = os.getenv(
    "QUESTION_BANK_API_URL",
    "https://api-dsa-python.onrender.com",
)
RUBRIC_API_URL: str = os.getenv(
    "RUBRIC_API_URL",
    "https://api-dsa-python.onrender.com/api/rubrics",
)
MY_SECRET_KEY: str = os.getenv("MY_SECRET_KEY", "default-key")


# ═══════════════════════════════════════════
#  Paths
# ═══════════════════════════════════════════
# config.py nằm tại  app/core/config.py  →  đi lên 3 cấp = project root
BASE_DIR: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
TESTCASE_ROOT: str = os.path.join(BASE_DIR, "testcases")


# ═══════════════════════════════════════════
#  AI Model Settings
# ═══════════════════════════════════════════
AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "gemini-2.0-flash")
AI_MODEL_TEMPERATURE: float = 0.1
AI_MAX_OUTPUT_TOKENS: int = 4096


# ═══════════════════════════════════════════
#  Grading Thresholds
# ═══════════════════════════════════════════
PLAGIARISM_THRESHOLD: float = 0.85
PASS_SCORE_THRESHOLD: int = 50
MAX_CONCURRENT_AI_CALLS: int = 50


# ═══════════════════════════════════════════
#  Application Constants
# ═══════════════════════════════════════════
MAX_HISTORY_ROWS: int = 2_000
JOB_TTL_SECONDS: int = 3_600          # Job hết hạn sau 1 giờ
DYNAMIC_TEST_TIMEOUT: int = 5         # Timeout test động (giây)


# ═══════════════════════════════════════════
#  Database (SQL Server — Optional)
# ═══════════════════════════════════════════
SQL_SERVER_CONNECTION: str = os.getenv("SQL_SERVER_CONNECTION", "")


# ═══════════════════════════════════════════
#  RAR Support (Optional Dependency)
# ═══════════════════════════════════════════
try:
    import rarfile as _rarfile        # noqa: F401
    RAR_SUPPORTED = True
except ImportError:
    _rarfile = None
    RAR_SUPPORTED = False
