from sqlalchemy.orm import Session
from sqlalchemy import func
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
            
            # Kiểm tra xem xe có trong Whitelist không
            # Chuẩn hóa biển số để so sánh (giống logic trong add_to_whitelist)
            clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
            normalized_db_plate = func.replace(func.replace(database.Whitelist.plate_number, '-', ''), '.', '')
            is_whitelisted = db.query(database.Whitelist).filter(normalized_db_plate == clean_plate).first()

            msg = "Check-out thành công"
            if is_whitelisted:
                session.fee = 0.0
                msg = "Check-out thành công (Xe ưu tiên - Miễn phí)"
            else:
                # Tính phí (fee) cho xe vãng lai
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
            return session, msg
        else:
            # Không tìm thấy xe trong bãi -> Từ chối Check-out để tránh lỗi
            msg = f"Xe {plate_number} chưa Check-in hoặc đã ra rồi!" if plate_number else "Không đọc được biển số để Check-out!"
            return None, msg

def get_recent_sessions(db: Session, limit: int = 100):
    """Lấy danh sách xe ra vào gần nhất (sắp xếp mới nhất lên đầu)"""
    return db.query(database.ParkingSession).order_by(database.ParkingSession.id.desc()).limit(limit).all()

def search_sessions_by_plate(db: Session, query: str, limit: int = 50):
    """Tìm kiếm xe theo biển số (gần đúng)"""
    # Tối ưu: Loại bỏ ký tự đặc biệt trong DB (dấu - và .) để so sánh với query đã chuẩn hóa
    # VD: DB có "30A-123.45" -> thành "30A12345" để khớp với query "12345"
    normalized_plate = func.replace(func.replace(database.ParkingSession.plate_number, '-', ''), '.', '')
    return db.query(database.ParkingSession).filter(
        normalized_plate.contains(query)
    ).order_by(database.ParkingSession.id.desc()).limit(limit).all()

def search_whitelist_by_plate(db: Session, query: str, limit: int = 50):
    """Tìm kiếm trong whitelist theo biển số (gần đúng)"""
    normalized_plate = func.replace(func.replace(database.Whitelist.plate_number, '-', ''), '.', '')
    return db.query(database.Whitelist).filter(
        normalized_plate.contains(query)
    ).limit(limit).all()

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

def delete_session(db: Session, session_id: int, upload_dir: str = None, crop_dir: str = None):
    """Xóa một session cụ thể và ảnh liên quan"""
    session = db.query(database.ParkingSession).filter(database.ParkingSession.id == session_id).first()
    if session:
        # Xóa file ảnh nếu có đường dẫn thư mục
        if upload_dir and crop_dir:
            if session.checkin_img:
                try: os.remove(os.path.join(upload_dir, session.checkin_img))
                except OSError: pass
                try: os.remove(os.path.join(crop_dir, f"crop_{session.checkin_img}"))
                except OSError: pass
            
            if session.checkout_img:
                try: os.remove(os.path.join(upload_dir, session.checkout_img))
                except OSError: pass
                try: os.remove(os.path.join(crop_dir, f"crop_{session.checkout_img}"))
                except OSError: pass
        
        db.delete(session)
        db.commit()
        return True
    return False

def update_session(db: Session, session_id: int, plate_number: str, status: str, fee: float):
    """Cập nhật thông tin session"""
    session = db.query(database.ParkingSession).filter(database.ParkingSession.id == session_id).first()
    if session:
        session.plate_number = plate_number
        session.status = status
        session.fee = fee
        db.commit()
        db.refresh(session)
        return session
    return None

# --- CÁC HÀM CHO CHỨC NĂNG WHITELIST (QUẢN LÝ RA VÀO) ---

def add_to_whitelist(db: Session, plate_number: str, owner_name: str, car_img: str = None):
    """Thêm biển số vào danh sách cho phép"""
    # Chuẩn hóa biển số (viết hoa, bỏ khoảng trắng)
    clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    
    # Kiểm tra tồn tại
    existing = db.query(database.Whitelist).filter(database.Whitelist.plate_number == clean_plate).first()
    if existing:
        return None, "Biển số này đã có trong danh sách!"
    
    item = database.Whitelist(plate_number=clean_plate, owner_name=owner_name, car_img=car_img)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, "Đã thêm vào danh sách thành công."

def check_whitelist(db: Session, plate_number: str):
    """Kiểm tra nhanh xem biển số có được phép không"""
    clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    normalized_db_plate = func.replace(func.replace(database.Whitelist.plate_number, '-', ''), '.', '')
    return db.query(database.Whitelist).filter(normalized_db_plate == clean_plate).first()

def get_all_whitelist(db: Session):
    """Lấy toàn bộ danh sách"""
    return db.query(database.Whitelist).all()

def delete_whitelist_entry(db: Session, plate_number: str):
    """Xóa khỏi danh sách"""
    db.query(database.Whitelist).filter(database.Whitelist.plate_number == plate_number).delete()
    db.commit()
