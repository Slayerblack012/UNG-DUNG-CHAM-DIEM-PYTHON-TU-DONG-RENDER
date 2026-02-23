"""
DSA AutoGrader — Entry Point.
Chạy file này để khởi động hệ thống. Trình duyệt sẽ tự mở.
"""

import webbrowser
import threading
import uvicorn

URL = "http://localhost:8000"


def open_browser():
    """Mở trình duyệt sau 1.5s (đợi server khởi động)."""
    import time
    time.sleep(1.5)
    webbrowser.open(URL)


if __name__ == "__main__":
    print()
    print("  ========================================")
    print("   DSA Grader - Dang khoi dong...")
    print("   Trinh duyet se tu dong mo.")
    print("   Nhan Ctrl+C de tat server.")
    print("  ========================================")
    print()

    # Mở browser trong thread riêng
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
