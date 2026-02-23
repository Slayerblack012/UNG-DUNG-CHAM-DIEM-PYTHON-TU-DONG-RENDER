-- ============================================
-- DSA AUTOGRADER - SQL SERVER DATABASE SETUP
-- Chạy script này trong SQL Server Management Studio
-- ============================================

-- 1. TẠO DATABASE (nếu chưa có)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'DSA_Grades')
BEGIN
    CREATE DATABASE DSA_Grades;
    PRINT N'✓ Đã tạo database DSA_Grades';
END
GO

USE DSA_Grades;
GO

-- 2. TẠO BẢNG SUBMISSIONS
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='submissions' AND xtype='U')
BEGIN
    CREATE TABLE submissions (
        -- Primary Key
        id INT IDENTITY(1,1) PRIMARY KEY,
        
        -- Thông tin sinh viên
        student_id NVARCHAR(50) NOT NULL,           -- Mã số sinh viên
        student_name NVARCHAR(255),                  -- Họ tên sinh viên
        
        -- Thông tin bài tập
        assignment_code NVARCHAR(100),               -- Mã bài tập (VD: BT01, LAB02)
        filename NVARCHAR(255) NOT NULL,             -- Tên file nộp
        topic NVARCHAR(100),                         -- Chủ đề (sorting, searching, ...)
        
        -- Điểm số chi tiết
        total_score FLOAT DEFAULT 0,                 -- Tổng điểm (0-100)
        pep8_score FLOAT DEFAULT 0,                  -- Điểm code style (0-10)
        dsa_score FLOAT DEFAULT 0,                   -- Điểm giải thuật (0-40)
        complexity_score FLOAT DEFAULT 0,            -- Điểm tối ưu (0-10)
        test_score FLOAT DEFAULT 0,                  -- Điểm test cases (0-40)
        
        -- Thông tin AI đánh giá
        algorithms NVARCHAR(255),                    -- Thuật toán phát hiện
        status NVARCHAR(20) DEFAULT 'PENDING',       -- PASS | FAIL | FLAG | PENDING
        feedback NVARCHAR(MAX),                      -- Nhận xét chi tiết từ AI
        runtime NVARCHAR(50),                        -- Thời gian xử lý
        
        -- Timestamps
        submitted_at DATETIME DEFAULT GETDATE(),    -- Thời điểm nộp bài
        graded_at DATETIME                          -- Thời điểm chấm xong
    );
    
    PRINT N'✓ Đã tạo bảng submissions';
END
GO

-- 3. TẠO INDEX CHO TÌM KIẾM NHANH
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_student_id')
    CREATE INDEX idx_student_id ON submissions(student_id);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_assignment_code')
    CREATE INDEX idx_assignment_code ON submissions(assignment_code);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_submitted_at')
    CREATE INDEX idx_submitted_at ON submissions(submitted_at DESC);

PRINT N'✓ Đã tạo indexes';
GO

-- 4. TẠO VIEW THỐNG KÊ
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_student_summary')
    DROP VIEW vw_student_summary;
GO

CREATE VIEW vw_student_summary AS
SELECT 
    student_id,
    student_name,
    COUNT(*) as total_submissions,
    AVG(total_score) as avg_score,
    MAX(total_score) as best_score,
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed_count,
    MAX(submitted_at) as last_submission
FROM submissions
GROUP BY student_id, student_name;
GO

PRINT N'✓ Đã tạo view vw_student_summary';
GO

-- 5. TẠO VIEW BÀI TẬP
IF EXISTS (SELECT * FROM sys.views WHERE name = 'vw_assignment_summary')
    DROP VIEW vw_assignment_summary;
GO

CREATE VIEW vw_assignment_summary AS
SELECT 
    assignment_code,
    COUNT(*) as total_submissions,
    AVG(total_score) as avg_score,
    MAX(total_score) as max_score,
    MIN(total_score) as min_score,
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) as failed,
    SUM(CASE WHEN status = 'FLAG' THEN 1 ELSE 0 END) as flagged
FROM submissions
WHERE assignment_code IS NOT NULL
GROUP BY assignment_code;
GO

PRINT N'✓ Đã tạo view vw_assignment_summary';
GO

-- ============================================
-- HOÀN TẤT
-- ============================================
PRINT N'';
PRINT N'========================================';
PRINT N'  DSA GRADES DATABASE - SẴN SÀNG SỬ DỤNG';
PRINT N'========================================';
PRINT N'';
PRINT N'Các bảng đã tạo:';
PRINT N'  - submissions: Lưu kết quả chấm điểm';
PRINT N'';
PRINT N'Các view:';
PRINT N'  - vw_student_summary: Thống kê theo sinh viên';
PRINT N'  - vw_assignment_summary: Thống kê theo bài tập';
GO


select * from dbo.submissions;