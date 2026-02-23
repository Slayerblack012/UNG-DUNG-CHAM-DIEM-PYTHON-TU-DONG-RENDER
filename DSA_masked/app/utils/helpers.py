"""
DSA AutoGrader — Utility Functions.
Các hàm tiện ích dùng chung cho toàn ứng dụng.
"""

import logging
from typing import Optional, Dict

import requests

from app.core.config import MY_SECRET_KEY, QUESTION_BANK_API_URL

logger = logging.getLogger("dsa.helpers")


def fetch_problem_from_bank(topic_id: str) -> Optional[Dict]:
    """
    Lấy thông tin đề bài từ Question Bank API.

    Args:
        topic_id: Mã chủ đề hoặc tên file (sẽ tự strip đuôi .py).

    Returns:
        Dict chứa thông tin đề bài, hoặc None nếu không tìm thấy.
    """
    if not topic_id:
        return None

    clean_id = topic_id.replace(".py", "").strip()
    url = f"{QUESTION_BANK_API_URL}/problems/{clean_id}"

    try:
        response = requests.get(
            url,
            headers={"x-api-key": MY_SECRET_KEY},
            timeout=10,
        )
        if response.status_code == 200:
            return response.json()

        logger.debug("Problem '%s' not found (HTTP %d).", clean_id, response.status_code)
        return None

    except requests.RequestException as exc:
        logger.warning("Failed to fetch problem '%s': %s", clean_id, exc)
        return None
