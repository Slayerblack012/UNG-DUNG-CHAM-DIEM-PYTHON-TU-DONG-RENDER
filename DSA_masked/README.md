# DSA Grader

**Hệ thống chấm điểm Cấu trúc dữ liệu & Giải thuật dành cho Sinh viên**

Hệ thống cung cấp nền tảng nộp bài và nhận phản hồi tức thì cho môn DSA.
Mô phỏng quy trình Code Review thực tế của giảng viên và Senior Developer: Nghiêm khắc, công bằng và chi tiết đến từng dòng code.

## Tổng quan

**DSA Grader** đóng vai trò như một môi trường Nộp bài & Nhận xét (LMS-style) chuyên biệt cho môn Cấu trúc Dữ liệu và Giải thuật.

Hệ thống không đánh giá dựa trên việc "code có chạy được hay không" (đó là yêu cầu tối thiểu). Thay vào đó, hệ thống tập trung phân tích mã nguồn
---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## Tính năng nổi bật

### 1. Giao diện Giáo dục (Education Theme)

- Thiết kế dạng Step-wizard (Từng bước rõ ràng: Thông tin -> File -> Báo cáo).
- Màu sắc chủ đạo Teal/Emerald thân thiện.
- Animation mượt mà, "staggered load" tạo cảm giác giống các hệ thống LMS lớn (Canvas, Google Classroom).

### 2. Tiêu chí Động (Dynamic Rubrics)

- Hệ thống hỗ trợ lấy tiêu chí chấm điểm tự động từ **Ngân hàng câu hỏi (Question Bank)**.
- Nếu bài tập chưa có cấu hình tiêu chí trên hệ thống, bài thi vẫn được phân tích logic và gợi ý thuật toán hoàn chỉnh nhưng sẽ ở trạng thái **Chờ tiêu chí (Pending)** — không tự ý cho điểm bừa.

### 3. Review Nghiêm khắc (Senior Dev Persona)

- Đánh giá trực diện: Chỉ rõ dòng code nào tồi, biến nào đặt tên chưa chuẩn.
- Gợi ý nâng cấp: Cung cấp hướng đi để biến code O(n²) thành O(n), kèm logic cụ thể.

### 4. Xử lý & Tích hợp

- Hỗ trợ `.py`, `.zip`, `.rar`.
- Cơ chế Webhook: Gửi callback tự động trả kết quả bài làm về hệ thống Quản lý đào tạo (LMS/Dashboard) của nhà trường khi quá trình chấm điểm kết thúc.

## Bắt đầu nhanh

### Yêu cầu hệ thống

| Thành phần | Yêu cầu               |
| ------------ | ----------------------- |
| Python       | >= 3.10                 |
| OS           | Windows / macOS / Linux |
| RAM          | >= 512 MB               |
| Port         | 8000 (mặc định)      |

### Cài đặt

```bash
# 1. Clone repository
git clone <repository-url>
cd DSA_masked

# 2. Cài đặt môi trường
pip install -r requirements.txt

# 3. Tạo file .env và cấu hình API Key (Xem mục Cấu hình)
```

### Cách chạy hệ thống

**Chạy môi trường Development (Có tự động mở trình duyệt):**

```bash
python main.py
```

> Hệ thống sẽ tự động mở trang web Nộp bài tại địa chỉ: `http://localhost:8000`

---

## Cấu hình

Tạo file `.env` tại thư mục gốc với các key sau:

```env
# Bat buoc neu muon nhan xet chuyen sau:
GEMINI_API_KEY=your_api_key_here

# Tuy chon:
PORT=8000
ENVIRONMENT=development
QUESTION_BANK_API_URL=https://api.truonghoc.edu.vn/dsa/kiemtra
```

---

## Kiến trúc Hệ thống

```text
+------------------------------------------------------+
|                 FRONTEND (UI)                         |
|  Step Wizard -> Drag & Drop -> Staggered Animations  |
+--------------------------+---------------------------+
                           | POST /grade (Cùng callback_url)
+--------------------------v---------------------------+
|                   API GATEWAY                        |
|                 (endpoints.py)                       |
+------------------------------------------------------+
|                  SERVICE LAYER                       |
|  +--------------+ +-------------+ +----------------+ |
|  |   Grader     | | API Client  | | File Processing| |
|  |  (Nghiêm khắc) | |(Rubric Bank) | |   (Zip/Rar)    | |
|  +------+-------+ +------+------+ +-------+--------+ |
+---------+----------------+------------------+--------+
|         |          DATA LAYER               |        |
|         v                v                  v        |
|  +--------------+ +--------------+ +-------------+ |
|  |  Score Store | |  Temp Files  | | Webhook Out | |
|  |  (JSON)      | |  (Disk)      | | (HTTP POST) | |
|  +--------------+ +--------------+ +-------------+ |
+------------------------------------------------------+
```

---

## Tiêu chí Chấm điểm (Rubric)

Điểm 80+ chỉ dành cho những đoạn code xứng đáng được merge vào môi trường Production.

| Tiêu chí                          | Điểm Max | Chi tiết                                                                    |
| ----------------------------------- | ---------- | ---------------------------------------------------------------------------- |
| **Logic (Logic_Score)**       | 40         | Code chạy sai logic trừ 15đ/lỗi. Thiếu Edge Case trừ 5-10đ.           |
| **Thuật toán (Algo_Score)** | 40         | Dùng Brute-force khi bài cần tối ưu sẽ bị trừ nặng (chỉ max 20đ). |
| **Coding Style**              | 10         | Trừ điểm biến vô nghĩa (`a, b, temp`), thiếu comment, PEP8 lỗi.    |
| **Tối ưu hóa**             | 10         | Trừ điểm nếu lặp code, import dư thừa.                                |

**Trạng thái chấm:**

- `PASS`: Đạt >= 50đ + Thỏa rubric.
- `FAIL`: < 50đ.
- `PENDING`: Ngân hàng câu hỏi chưa có rubric — chỉ trả về Feedback phân tích.

---

## Tích hợp / Webhook

Các hệ thống Dashboard của Sinh viên hoặc Quản lý Đào tạo có thể tích hợp qua Webhook thay vì Polling liên tục.

### `POST /grade`

**Request (FormData):**

- `files`: Tệp bài làm (`.py`, `.zip`, `.rar`)
- `student_name`: Tên sinh viên
- `callback_url`: URL webhook để hệ thống báo kết quả về. (Ví dụ: `https://lms.truong.edu.vn/api/webhook/dsa-grades`)

**Luồng hoạt động:**

1. Sinh viên nhấn "Nộp Bài" trên LMS.
2. LMS gọi API `POST /grade` truyền theo `callback_url`.
3. DSA Grader phản hồi mức `200 OK` (Job Accepted) ngay lập tức.
4. DSA Grader chấm bài chạy nền trong vòng vài giây.
5. Khi hoàn tất, DSA Grader tự động bắn 1 `POST` request chứa toàn bộ JSON điểm số và nhận xét chi tiết về `callback_url`.

---

## License

```text
Copyright (c) 2026 DSA Masked OS. All rights reserved.
DEMO BY TRAN VAN HUNG AND HUYNH MINH SANG
22CT111-LAC-HONG-UNIVERSITY
```

---
