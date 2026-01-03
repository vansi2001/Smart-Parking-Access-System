import os
import time
import re
from fastapi import FastAPI, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
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
