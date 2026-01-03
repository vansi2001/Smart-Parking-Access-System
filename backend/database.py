from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 1. Cấu hình SQLite (File database sẽ tên là parking.db)
SQLALCHEMY_DATABASE_URL = "sqlite:///./parking.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Định nghĩa Bảng dữ liệu (Model)
class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, index=True) # Index giúp tìm biển số nhanh hơn
    
    checkin_time = Column(DateTime, default=datetime.now) # Tự lấy giờ hiện tại
    checkout_time = Column(DateTime, nullable=True)       # Lúc đầu chưa có giờ ra
    
    status = Column(String, default="PARKING") # Mặc định là đang gửi
    
    checkin_img = Column(String, nullable=True)
    checkout_img = Column(String, nullable=True)
    
    fee = Column(Float, default=0.0)

# 3. Hàm tạo bảng (Chạy 1 lần đầu để sinh file .db)
def init_db():
    Base.metadata.create_all(bind=engine)
    print("Đã tạo xong database parking.db!")

# Hàm tiện ích để lấy kết nối DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
