import os
import time
import re
import csv
import codecs
import cv2
from datetime import datetime
from io import BytesIO
from fastapi import FastAPI, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

# Tạo thư mục con cho ảnh whitelist
WHITELIST_DIR = os.path.join(UPLOAD_DIR, 'whitelist_image')
os.makedirs(WHITELIST_DIR, exist_ok=True)

# Mount thư mục uploads để xem ảnh qua URL /static/
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

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
    confirmed: int = Form(0),       # 0: Chưa xác nhận, 1: Đã xác nhận (cho xe vãng lai)
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

    size = len(content)
    
    # Xử lý biển số: Ưu tiên nhập tay, nếu không có mới chạy AI
    plate_text = None
    cropped_path = None
    cropped_img = None
    crop_msg = ""
    
    if plate_number:
        plate_text = plate_number.strip().upper()
        crop_msg = "手動輸入車牌"
    else:
        # Tiến hành cắt ảnh xe (nếu có)
        cropped_img = yolo_utils.detect_and_crop_vehicle(content)
        crop_msg = "找不到車輛"
        if cropped_img is not None:
            crop_msg = "已裁切車輛影像"
            # Tiến hành OCR với ảnh đã cắt sẵn trong RAM (cropped_img)
            plate_text = yolo_utils.read_plate_text(cropped_img)

    # --- VALIDATION: Kiểm tra định dạng biển số ---
    # 1. Nếu không đọc được biển số
    if not plate_text:
        return {
            "success": False,
            "id": None,
            "cropped_image": None,
            "plate_number": None,
            "fee": 0,
            "message": "⚠️ 無法讀取車牌！請重新拍攝。"
        }

    # 2. Kiểm tra regex định dạng: Chấp nhận cả 5 số (có chấm) và 4 số
    # Ví dụ hợp lệ: 30A-123.45 HOẶC 30A-1234
    if not re.match(r'^\d{2}[A-Z]-(\d{3}\.\d{2}|\d{4})$', plate_text):
        return {
            "success": False,
            "id": None,
            "cropped_image": None,
            "plate_number": plate_text,
            "fee": 0,
            "message": f"⚠️ 車牌格式錯誤: {plate_text}。請使用正確格式 (例如: 30A-123.45 或 30A-1234)"
        }

    # --- LOGIC MỚI: KIỂM TRA XE VÃNG LAI (CHỈ ÁP DỤNG KHI CHECK-IN) ---
    if int(status) == 1:
        # Kiểm tra whitelist
        is_whitelisted = crud.check_whitelist(db, plate_text)
        
        # Nếu KHÔNG phải whitelist VÀ CHƯA được xác nhận (confirmed=0)
        if not is_whitelisted and confirmed == 0:
            return {
                "success": False,
                "need_confirmation": True, # Cờ báo hiệu cho FE
                "plate_number": plate_text,
                "message": f"⚠️ 訪客車輛: {plate_text}。需確認後方可進入。"
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
            "cropped_image": None,
            "plate_number": plate_text,
            "fee": 0,
            "message": f"⚠️ {msg}"
        }

    # --- THÀNH CÔNG: BÂY GIỜ MỚI LƯU FILE ---
    # 1. Lưu ảnh gốc
    with open(dest_path, 'wb') as f:
        f.write(content)

    # 2. Lưu ảnh crop (nếu có)
    if cropped_img is not None:
        crop_name = f"crop_{safe_name}"
        cropped_path = os.path.join(CROP_DIR, crop_name)
        cv2.imwrite(cropped_path, cropped_img)

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
        return {"success": False, "message": "驗證碼錯誤！"}

    try:
        # Convert string ISO format từ frontend thành datetime
        dt_start = datetime.fromisoformat(start_time)
        dt_end = datetime.fromisoformat(end_time)
    except ValueError:
        return {"success": False, "message": "時間格式無效"}

    # 2. Lấy dữ liệu
    sessions = crud.get_sessions_in_range(db, dt_start, dt_end)
    
    if not sessions:
        return {"success": False, "message": "此期間無資料"}

    # 3. Tạo file Excel bằng openpyxl
    try:
        import openpyxl
    except ImportError:
        return {"success": False, "message": "伺服器錯誤: 未安裝 'openpyxl' 函式庫。請執行: pip install openpyxl"}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "停車報表"
    
    # Header
    headers = ["ID", "車牌", "入場時間", "出場時間", "狀態", "費用 (VNĐ)", "入場照片", "出場照片"]
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

# --- CÁC API MỚI CHO CHỨC NĂNG "PARKING CONTROL WIDGET" ---

@app.get("/api/sessions")
def read_sessions(limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách lịch sử ra vào cho Admin Dashboard"""
    return crud.get_recent_sessions(db, limit)

@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: int, db: Session = Depends(get_db)):
    """Xóa một lượt gửi xe"""
    success = crud.delete_session(db, session_id, UPLOAD_DIR, CROP_DIR)
    if success:
        return {"success": True, "message": "已成功刪除紀錄"}
    return {"success": False, "message": "找不到紀錄"}

@app.put("/api/sessions/{session_id}")
async def update_session_endpoint(
    session_id: int,
    plate_number: str = Form(...),
    status: str = Form(...),
    fee: float = Form(...),
    db: Session = Depends(get_db)
):
    """Cập nhật thông tin lượt gửi xe"""
    updated = crud.update_session(db, session_id, plate_number, status, fee)
    if updated:
        return {"success": True, "message": "更新成功"}
    return {"success": False, "message": "更新失敗或找不到 ID"}

@app.get("/api/search")
def search_vehicle(query: str, db: Session = Depends(get_db)):
    """
    Tìm kiếm xe theo biển số và trả về thông tin chi tiết (kèm trạng thái Whitelist).
    """
    # Tối ưu: Xóa khoảng trắng, gạch ngang, dấu chấm để tìm linh hoạt (VD: "30A-123" -> "30A123")
    clean_query = query.strip().upper().replace(" ", "").replace("-", "").replace(".", "")
    
    # 1. Tìm trong lịch sử ra vào (ParkingSession)
    sessions = crud.search_sessions_by_plate(db, clean_query)
    
    results = []
    # Xử lý kết quả từ lịch sử
    for s in sessions:
        # 2. Kiểm tra xem xe này có trong Whitelist không
        wl_item = crud.check_whitelist(db, s.plate_number)
        
        is_whitelist = True if wl_item else False
        owner_info = wl_item.owner_name if wl_item else "訪客"
        
        results.append({
            "id": s.id,
            "plate_number": s.plate_number,
            "checkin_time": s.checkin_time,
            "checkout_time": s.checkout_time,
            "status": s.status,
            "fee": s.fee,
            "checkin_img": s.checkin_img,
            "checkout_img": s.checkout_img,
            "is_whitelist": is_whitelist,
            "owner_name": owner_info
        })

    # 2. Tìm thêm trong Whitelist (để tìm những xe chưa gửi lần nào hoặc không có trong history gần nhất)
    # Chỉ tìm nếu kết quả history ít hoặc để bổ sung
    whitelist_hits = crud.search_whitelist_by_plate(db, clean_query)
    
    # Lấy danh sách biển số đã có trong results để tránh trùng lặp
    existing_plates = {r["plate_number"] for r in results}

    for w in whitelist_hits:
        if w.plate_number not in existing_plates:
            results.append({
                "id": f"WL-{w.id}", # ID giả định
                "plate_number": w.plate_number,
                "checkin_time": None,
                "checkout_time": None,
                "status": "NO_SESSION", # Trạng thái đặc biệt: Chưa gửi xe
                "fee": 0,
                "checkin_img": w.car_img, # Dùng ảnh đăng ký làm ảnh checkin để hiển thị
                "checkout_img": None,
                "is_whitelist": True,
                "owner_name": w.owner_name
            })

    return results

@app.post("/api/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    """API Đăng nhập cho Admin"""
    # Trong thực tế nên lưu user trong DB và mã hóa mật khẩu
    # Ở đây demo hardcode: admin / admin123
    if username == "admin" and password == "admin123":
        return {"success": True, "token": "fake_token_secure_123", "message": "登入成功！"}
    return {"success": False, "message": "使用者名稱或密碼錯誤！"}

@app.post("/api/check-access")
async def check_access_manual(
    plate_number: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    API cho nhân viên nhập tay biển số để kiểm tra nhanh.
    Input: Biển số xe (VD: 30A-123.45)
    Output: Cho phép (Xanh) hoặc Từ chối (Đỏ)
    """
    # Tìm trong whitelist
    item = crud.check_whitelist(db, plate_number)
    
    if item:
        return {
            "allowed": True,
            "color": "green",
            "message": f"✅ 允許進入\n車主: {item.owner_name}",
            "plate_number": item.plate_number
        }
    else:
        return {
            "allowed": False,
            "color": "red",
            "message": "⛔ 不在清單中\n請重新檢查或收取訪客費用。",
            "plate_number": plate_number
        }

@app.get("/api/whitelist")
def get_whitelist(db: Session = Depends(get_db)):
    """Lấy danh sách xe được phép"""
    return crud.get_all_whitelist(db)

@app.post("/api/whitelist")
async def add_whitelist(
    plate_number: str = Form(...),
    owner_name: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """Thêm xe vào danh sách"""
    car_img_name = None
    dest_path = None
    # Chỉ xử lý nếu có file và file có tên (tránh trường hợp gửi file rỗng)
    if image and image.filename:
        # Lưu ảnh chủ xe vào thư mục uploads
        ts = int(time.time())
        filename = os.path.basename(image.filename)
        safe_name = f"{ts}_{filename}"
        dest_path = os.path.join(WHITELIST_DIR, safe_name)
        content = await image.read()
        with open(dest_path, 'wb') as f:
            f.write(content)
        car_img_name = f"whitelist_image/{safe_name}"

    item, msg = crud.add_to_whitelist(db, plate_number, owner_name, car_img_name)
    if not item:
        # Nếu thêm thất bại (VD: trùng biển số), xóa ảnh vừa lưu để tránh rác
        if dest_path and os.path.exists(dest_path):
            os.remove(dest_path)
        return {"success": False, "message": msg}
    return {"success": True, "message": msg, "data": item}

@app.post("/api/whitelist/import")
async def import_whitelist_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Nhập danh sách Whitelist từ file CSV"""
    if not file.filename.endswith('.csv'):
        return {"success": False, "message": "請選擇 .csv 檔案"}

    content = await file.read()
    # Giải mã file CSV (xử lý BOM nếu có để tránh lỗi ký tự đầu)
    decoded_content = content.decode("utf-8-sig").splitlines()
    reader = csv.reader(decoded_content)

    count_success = 0
    count_fail = 0
    
    for row in reader:
        # Bỏ qua dòng trống hoặc không đủ dữ liệu tối thiểu (Biển số, Tên)
        if not row or len(row) < 2:
            continue
            
        plate = row[0].strip()
        owner = row[1].strip()
        img_path = row[2].strip() if len(row) > 2 else None
        
        item, msg = crud.add_to_whitelist(db, plate, owner, img_path)
        if item:
            count_success += 1
        else:
            count_fail += 1

    return {
        "success": True, 
        "message": f"完成！成功: {count_success}, 略過 (重複/錯誤): {count_fail}"
    }
