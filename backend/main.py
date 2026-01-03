import os
import time
import re
from datetime import datetime
from io import BytesIO
from fastapi import FastAPI, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import crud, models, yolo_utils
from database import SessionLocal, engine, get_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ensure uploads folder exists
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# create crops folder
CROP_DIR = os.path.join(os.path.dirname(__file__), 'crops')
os.makedirs(CROP_DIR, exist_ok=True)

# create DB tables
# models.Base refers to the Base imported in models.py from database.py
models.Base.metadata.create_all(bind=engine)


@app.post('/upload')
async def upload_image(
    image: UploadFile = File(...), 
    status: int = Form(...), 
    plate_number: str = Form(None), # Nhận thêm biển số nhập tay (Optional)
    db: Session = Depends(get_db)
):
    """Receive uploaded image and a status field (1=checkin,0=checkout).
    Saves file to `uploads/` and inserts a record into SQLite DB.
    """
    # --- DEBUG: In ra ngay khi nhận được request ---
    print(f"📡 ĐANG NHẬN REQUEST: Filename='{image.filename}', Status={status}")

    content = await image.read()
    ts = int(time.time())
    safe_name = f"{ts}_{os.path.basename(image.filename)}"
    dest_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(dest_path, 'wb') as f:
        f.write(content)

    size = len(content)
    
    # Xử lý biển số: Ưu tiên nhập tay, nếu không có mới chạy AI
    plate_text = None
    cropped_path = None
    crop_msg = ""
    
    if plate_number:
        plate_text = plate_number.strip().upper()
        crop_msg = "Biển số nhập tay từ Frontend"
    else:
        # Tiến hành cắt ảnh xe (nếu có)
        cropped_path, cropped_img = yolo_utils.detect_and_crop_vehicle(content, safe_name, CROP_DIR)
        crop_msg = "Không tìm thấy xe"
        if cropped_path:
            crop_msg = f"Đã cắt ảnh xe: {os.path.basename(cropped_path)}"
            # Tiến hành OCR với ảnh đã cắt sẵn trong RAM (cropped_img)
            plate_text = yolo_utils.read_plate_text(cropped_img)

    # --- VALIDATION: Kiểm tra định dạng biển số ---
    # 1. Nếu không đọc được biển số
    if not plate_text:
        return {
            "success": False,
            "id": None,
            "cropped_image": os.path.basename(cropped_path) if cropped_path else None,
            "plate_number": None,
            "fee": 0,
            "message": "⚠️ Không đọc được biển số! Vui lòng chụp lại."
        }

    # 2. Kiểm tra regex định dạng 5 số: 2 số + 1 chữ + '-' + 3 số + '.' + 2 số
    # Ví dụ hợp lệ: 30A-123.45. Ví dụ không hợp lệ: 30A-1234 (4 số), 06A-4253 (4 số)
    if not re.match(r'^\d{2}[A-Z]-\d{3}\.\d{2}$', plate_text):
        return {
            "success": False,
            "id": None,
            "cropped_image": os.path.basename(cropped_path) if cropped_path else None,
            "plate_number": plate_text,
            "fee": 0,
            "message": f"⚠️ Biển số sai định dạng: {plate_text}. Yêu cầu biển 5 số (VD: 30A-123.45)"
        }

    # SAU KHI xử lý ảnh xong, mới tiến hành lưu vào DB
    # Kết hợp status, tên file ảnh và biển số vừa đọc được
    rec, msg = crud.create_session_entry(db, safe_name, int(status), plate_text)

    # Nếu bị từ chối (rec is None) do trùng lặp hoặc không tìm thấy xe
    if not rec:
        print(f"⚠️ TỪ CHỐI: {msg}")
        return {
            "success": False,
            "id": None,
            "cropped_image": os.path.basename(cropped_path) if cropped_path else None,
            "plate_number": plate_text,
            "fee": 0,
            "message": f"⚠️ {msg}"
        }

    print(f"Đã nhận ảnh: {size} bytes, status={status}. {crop_msg}. Biển số: {plate_text}. Msg: {msg}")
    return {
        "success": True, 
        "id": rec.id, 
        "cropped_image": os.path.basename(cropped_path) if cropped_path else None,
        "plate_number": plate_text,
        "fee": rec.fee if rec.fee else 0,
        "message": msg
    }

@app.post('/report')
async def export_report(
    start_time: str = Form(...),
    end_time: str = Form(...),
    secret_code: str = Form(...),
    delete_data: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Xuất báo cáo Excel và tùy chọn xóa dữ liệu"""
    # 1. Kiểm tra mã bảo mật
    if secret_code != "123":
        return {"success": False, "message": "Mã xác nhận không đúng!"}

    try:
        # Convert string ISO format từ frontend thành datetime
        dt_start = datetime.fromisoformat(start_time)
        dt_end = datetime.fromisoformat(end_time)
    except ValueError:
        return {"success": False, "message": "Định dạng thời gian không hợp lệ"}

    # 2. Lấy dữ liệu
    sessions = crud.get_sessions_in_range(db, dt_start, dt_end)
    
    if not sessions:
        return {"success": False, "message": "Không có dữ liệu trong khoảng thời gian này"}

    # 3. Tạo file Excel bằng openpyxl
    try:
        import openpyxl
    except ImportError:
        return {"success": False, "message": "Lỗi Server: Chưa cài thư viện 'openpyxl'. Vui lòng chạy: pip install openpyxl"}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Báo cáo gửi xe"
    
    # Header
    headers = ["ID", "Biển số", "Giờ vào", "Giờ ra", "Trạng thái", "Phí (VNĐ)", "Ảnh vào", "Ảnh ra"]
    ws.append(headers)
    
    for s in sessions:
        ws.append([
            s.id,
            s.plate_number,
            s.checkin_time.strftime("%Y-%m-%d %H:%M:%S") if s.checkin_time else "",
            s.checkout_time.strftime("%Y-%m-%d %H:%M:%S") if s.checkout_time else "",
            s.status,
            s.fee,
            s.checkin_img,
            s.checkout_img
        ])

    # 4. Xóa dữ liệu nếu được yêu cầu (Sau khi đã đưa vào excel)
    deleted_count = 0
    if delete_data:
        deleted_count = crud.delete_sessions_in_range(db, dt_start, dt_end, UPLOAD_DIR, CROP_DIR)
        print(f"Đã xóa {deleted_count} bản ghi và giải phóng dung lượng.")

    # 5. Trả về file Excel
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    filename = f"BaoCao_{dt_start.strftime('%Y%m%d')}_{dt_end.strftime('%Y%m%d')}.xlsx"
    
    # Trả về file stream
    return StreamingResponse(
        buffer, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
