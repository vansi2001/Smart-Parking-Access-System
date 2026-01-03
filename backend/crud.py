from sqlalchemy.orm import Session
import models, database
from datetime import datetime
import os


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
        # Xe vào: Kiểm tra xem xe đã có trong bãi chưa (tránh Check-in 2 lần)
        if plate_number:
            existing = db.query(database.ParkingSession).filter(
                database.ParkingSession.plate_number == plate_number,
                database.ParkingSession.status == "PARKING"
            ).first()
            if existing:
                return None, f"Xe {plate_number} đang trong bãi! Không thể Check-in lại."

        # Xe vào: Tạo session mới
        session = database.ParkingSession(
            plate_number=plate_number,
            checkin_img=filename,
            checkin_time=datetime.now(),
            status="PARKING"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session, "Check-in thành công"
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
            
            db.commit()
            db.refresh(session)
            return session, "Check-out thành công"
        else:
            # Không tìm thấy xe trong bãi -> Từ chối Check-out để tránh lỗi
            msg = f"Xe {plate_number} chưa Check-in hoặc đã ra rồi!" if plate_number else "Không đọc được biển số để Check-out!"
            return None, msg

def get_sessions_in_range(db: Session, start_date: datetime, end_date: datetime):
    """Lấy danh sách session trong khoảng thời gian (dựa theo checkin_time)"""
    return db.query(database.ParkingSession).filter(
        database.ParkingSession.checkin_time >= start_date,
        database.ParkingSession.checkin_time <= end_date
    ).all()

def delete_sessions_in_range(db: Session, start_date: datetime, end_date: datetime, upload_dir: str, crop_dir: str):
    """Xóa session và file ảnh liên quan trong khoảng thời gian"""
    sessions = get_sessions_in_range(db, start_date, end_date)
    count = 0
    
    for ses in sessions:
        # Xóa file ảnh checkin
        if ses.checkin_img:
            try: os.remove(os.path.join(upload_dir, ses.checkin_img))
            except OSError: pass
            try: os.remove(os.path.join(crop_dir, f"crop_{ses.checkin_img}"))
            except OSError: pass
            
        # Xóa file ảnh checkout
        if ses.checkout_img:
            try: os.remove(os.path.join(upload_dir, ses.checkout_img))
            except OSError: pass
            try: os.remove(os.path.join(crop_dir, f"crop_{ses.checkout_img}"))
            except OSError: pass

        db.delete(ses)
        count += 1
    
    db.commit()
    return count
