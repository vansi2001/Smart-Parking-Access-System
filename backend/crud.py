from sqlalchemy.orm import Session
import models, database
from datetime import datetime


def create_record(db: Session, filename: str, status: int, size: int = None):
    """Giữ lại hàm này nếu muốn duy trì bảng log cũ (ParkingRecord)"""
    rec = models.ParkingRecord(filename=filename, status=int(status), size=size)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

def create_session_entry(db: Session, filename: str, status: int, plate_number: str = None):
    """Tạo bản ghi vào bảng chính ParkingSession"""
    # status: 1 = Check-in, 0 = Check-out
    if status == 1:
        # Xe vào: Tạo session mới
        session = database.ParkingSession(
            plate_number=plate_number,
            checkin_img=filename,
            checkin_time=datetime.now(),
            status="PARKING"
        )
        db.add(session)
    else:
        # Xe ra: Tìm session đang mở (PARKING) có cùng biển số
        session = None
        if plate_number:
            session = db.query(database.ParkingSession).filter(
                database.ParkingSession.plate_number == plate_number,
                database.ParkingSession.status == "PARKING"
            ).first()
        
        if session:
            # Tìm thấy xe đang gửi -> Cập nhật thông tin ra
            session.checkout_img = filename
            session.checkout_time = datetime.now()
            session.status = "CHECKOUT"
            
            # Tính phí (fee)
            duration = session.checkout_time - session.checkin_time
            hours = duration.total_seconds() / 3600.0
            
            if hours <= 4:      # 1 lượt (ví dụ dưới 4 tiếng)
                session.fee = 5000.0
            elif hours <= 12:   # 1 ngày
                session.fee = 30000.0
            else:               # 1 ngày đêm
                session.fee = 50000.0
        else:
            # Không tìm thấy (hoặc không đọc được biển) -> Tạo record rời rạc
            session = database.ParkingSession(
                plate_number=plate_number,
                checkout_img=filename,
                checkout_time=datetime.now(),
                status="CHECKOUT"
            )
            db.add(session)
    
    db.commit()
    db.refresh(session)
    return session
