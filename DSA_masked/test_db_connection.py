"""
Test kết nối SQL Server
Chạy: python test_db_connection.py
"""

import pyodbc

# Cấu hình - chỉnh theo SQL Server của bạn
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=DSA_Grades;"
    "UID=sa;"
    "PWD=1;"
    "TrustServerCertificate=yes;"
)

def test_connection():
    print("=" * 50)
    print("🔌 TEST KẾT NỐI SQL SERVER")
    print("=" * 50)
    
    try:
        print("\n📡 Đang kết nối...")
        conn = pyodbc.connect(CONNECTION_STRING, timeout=5)
        print("✅ KẾT NỐI THÀNH CÔNG!")
        
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"\n📊 SQL Server Version:\n{version[:100]}...")
        
        # Check database
        cursor.execute("SELECT DB_NAME()")
        db_name = cursor.fetchone()[0]
        print(f"\n🗄️ Database hiện tại: {db_name}")
        
        # Check if submissions table exists
        cursor.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'submissions'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        if table_exists:
            print("✅ Bảng 'submissions' đã tồn tại")
            cursor.execute("SELECT COUNT(*) FROM submissions")
            count = cursor.fetchone()[0]
            print(f"📝 Số bản ghi hiện có: {count}")
        else:
            print("⚠️ Bảng 'submissions' chưa tồn tại")
            print("   Chạy script: scripts/setup_database.sql trong SSMS")
        
        conn.close()
        print("\n" + "=" * 50)
        print("🎉 TEST HOÀN TẤT - SẴN SÀNG SỬ DỤNG!")
        print("=" * 50)
        return True
        
    except pyodbc.InterfaceError as e:
        print(f"\n❌ LỖI DRIVER: {e}")
        print("\n💡 Giải pháp:")
        print("   1. Cài đặt ODBC Driver 17 for SQL Server:")
        print("      https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
        return False
        
    except pyodbc.OperationalError as e:
        print(f"\n❌ LỖI KẾT NỐI: {e}")
        print("\n💡 Kiểm tra:")
        print("   1. SQL Server có đang chạy không?")
        print("   2. Tên SERVER có đúng không?")
        print("   3. Port 1433 có mở không?")
        return False
        
    except pyodbc.ProgrammingError as e:
        print(f"\n❌ LỖI DATABASE: {e}")
        print("\n💡 Giải pháp:")
        print("   1. Chạy script: scripts/setup_database.sql")
        print("   2. Tạo database 'DSA_Grades' thủ công")
        return False
        
    except Exception as e:
        print(f"\n❌ LỖI: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    test_connection()
