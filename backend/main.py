import os
import time
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
async def upload_image(image: UploadFile = File(...), status: int = Form(...), db: Session = Depends(get_db)):
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
    
    # Tiến hành cắt ảnh xe (nếu có)
    cropped_path = yolo_utils.detect_and_crop_vehicle(dest_path, CROP_DIR)
    crop_msg = "Không tìm thấy xe"
    plate_text = None
    
    if cropped_path:
        crop_msg = f"Đã cắt ảnh xe: {os.path.basename(cropped_path)}"
        # Tiến hành OCR để đọc biển số
        plate_text = yolo_utils.read_plate_text(cropped_path)

    # SAU KHI xử lý ảnh xong, mới tiến hành lưu vào DB
    # Kết hợp status, tên file ảnh và biển số vừa đọc được
    rec = crud.create_session_entry(db, safe_name, int(status), plate_text)

    # Logic tạo thông báo phản hồi
    message = "Thành công"
    # Nếu là Check-out (0) mà phí = 0 -> Có nghĩa là không tìm thấy xe vào
    if int(status) == 0 and (rec.fee is None or rec.fee == 0):
        message = "⚠️ CẢNH BÁO: Không tìm thấy thông tin xe vào! Vui lòng kiểm tra thủ công."

    print(f"Đã nhận ảnh: {size} bytes, status={status}. {crop_msg}. Biển số: {plate_text}")
    return {
        "success": True, 
        "id": rec.id, 
        "cropped_image": os.path.basename(cropped_path) if cropped_path else None,
        "plate_number": plate_text,
        "fee": rec.fee if rec.fee else 0,
        "message": message
    }
