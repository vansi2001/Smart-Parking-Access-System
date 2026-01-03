import cv2
import os
from ultralytics import YOLO
import easyocr
import numpy as np
import re
import torch

# Load model YOLOv8 nano (sẽ tự động tải file yolov8n.pt về thư mục hiện tại nếu chưa có)
# Model này nhận diện được 80 loại đối tượng trong bộ dữ liệu COCO
model = YOLO("yolov8n.pt")

# Khởi tạo EasyOCR (chỉ tải model lần đầu chạy)
# TỰ ĐỘNG KIỂM TRA GPU: Nếu có CUDA thì dùng GPU, ngược lại dùng CPU
use_gpu = torch.cuda.is_available()
reader = easyocr.Reader(['en'], gpu=use_gpu)

# Danh sách class ID của các loại xe trong COCO dataset
# 2: car, 3: motorcycle, 5: bus, 7: truck
VEHICLE_CLASSES = [2, 3, 5, 7]

def detect_and_crop_vehicle(image_data):
    """
    Nhận diện xe từ dữ liệu ảnh (bytes) và cắt ảnh xe.
    Trả về ảnh cắt dạng numpy array (hoặc None).
    """
    # Đọc ảnh trực tiếp từ bộ nhớ (Memory) thay vì đọc lại từ đĩa
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return None

    # --- TỐI ƯU HÓA 1: Resize ảnh lớn xuống kích thước vừa phải để YOLO chạy nhanh hơn ---
    # YOLOv8n được train ở 640x640. Resize về 640 giúp tăng tốc độ gấp 2-4 lần so với 1280
    height, width = img.shape[:2]
    if width > 640:
        scale = 640 / width
        img = cv2.resize(img, None, fx=scale, fy=scale)

    # Chạy dự đoán
    results = model(img, verbose=False)
    
    # Lấy kết quả đầu tiên (vì ta chỉ xử lý 1 ảnh)
    result = results[0]
    
    # Tìm box có độ tin cậy cao nhất thuộc nhóm xe
    best_box = None
    max_conf = 0.0

    for box in result.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        
        if cls_id in VEHICLE_CLASSES and conf > max_conf:
            max_conf = conf
            best_box = box.xyxy[0].cpu().numpy() # toạ độ [x1, y1, x2, y2]

    if best_box is not None:
        x1, y1, x2, y2 = map(int, best_box)
        
        # Cắt ảnh (Crop)
        crop_img = img[y1:y2, x1:x2]
        
        return crop_img
    
    return None

def read_plate_text(image_source) -> str:
    """
    Đọc văn bản từ ảnh (có thể là đường dẫn file hoặc numpy array).
    """
    img = None
    if isinstance(image_source, str):
        # Nếu là đường dẫn file
        if os.path.exists(image_source):
            img = cv2.imread(image_source)
    else:
        # Nếu là ảnh numpy array (đã load sẵn)
        img = image_source

    if img is None:
        return None

    # 1. Xử lý ảnh (Preprocessing) - TỐI ƯU HÓA TỐC ĐỘ
    # Chỉ phóng to nếu ảnh quá nhỏ (chiều ngang < 300px)
    # Ảnh từ điện thoại cắt ra thường đã đủ lớn, phóng to thêm sẽ làm chậm OCR rất nhiều
    h, w = img.shape[:2]
    if w < 300:
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Bỏ bilateralFilter vì rất chậm, thay bằng GaussianBlur nhẹ hơn nếu cần, hoặc bỏ qua
    # gray = cv2.GaussianBlur(gray, (3, 3), 0) 
    
    # 2. Đọc text (detail=0 chỉ lấy nội dung text)
    # TỐI ƯU HÓA 2: Thêm tham số decoder='greedy' (nhanh hơn beamsearch)
    # batch_size=1: Giảm độ trễ cho 1 ảnh đơn lẻ
    results = reader.readtext(gray, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.', decoder='greedy', batch_size=1)
    
    # 3. Hậu xử lý (Post-processing) theo định dạng biển số VN
    if results:
        # Nối tất cả text lại thành 1 chuỗi liền mạch, loại bỏ dấu câu để dễ tìm pattern
        # Ví dụ OCR ra: ['HOND', '30A', '-', '123.45'] -> "HOND30A12345"
        full_text = "".join(results).upper().replace(" ", "").replace(".", "").replace("-", "")
        
        # Regex tìm chuỗi tiềm năng:
        # Tìm chuỗi ký tự liên tiếp có độ dài 7-9 ký tự (bao gồm cả chữ và số)
        # Sau đó sẽ dùng hàm fix_vietnamese_plate_format để ép kiểu từng vị trí
        pattern = r'[A-Z0-9]{7,9}'
        
        matches = re.findall(pattern, full_text)
        
        # Nếu tìm thấy pattern khớp, lấy kết quả cuối cùng (thường biển số nằm ở cuối/giữa ảnh)
        if matches:
            candidate = matches[-1]
            return fix_vietnamese_plate_format(candidate)
        
        # Fallback: Nếu không khớp pattern nào, thử sửa toàn bộ chuỗi (ít chính xác hơn)
        clean_text = re.sub(r'[^A-Z0-9]', '', full_text)
        if 7 <= len(clean_text) <= 9:
            return fix_vietnamese_plate_format(clean_text)
            
    return None

def fix_vietnamese_plate_format(text: str) -> str:
    """
    Chuẩn hóa biển số xe Việt Nam (Dân sự: 2 Số - 1 Chữ - 4/5 Số)
    Ví dụ input: "3OA12345" -> output: "30A12345"
    """
    # Nếu chuỗi quá dài (>8), ta cần chọn ra 8 ký tự "giống biển số nhất"
    # Thay vì chỉ lấy text[:8] (dễ bị dính ký tự rác ở đầu làm mất số cuối),
    # ta dùng Sliding Window để tìm đoạn khớp mẫu: DD C DDDDD
    if len(text) > 8:
        best_text = text[:8]
        best_score = -1
        
        for i in range(len(text) - 8 + 1):
            sub = text[i:i+8]
            score = 0
            # Cộng điểm nếu ký tự đúng loại (Số ở vị trí số, Chữ ở vị trí chữ)
            if sub[0].isdigit(): score += 1
            if sub[1].isdigit(): score += 1
            if sub[2].isalpha(): score += 1
            for j in range(3, 8):
                if sub[j].isdigit(): score += 1
            
            if score > best_score:
                best_score = score
                best_text = sub
        
        text = best_text

    # Biển số thường có từ 7 đến 8 ký tự (bao gồm cả mã tỉnh, series và số)
    if len(text) < 7:
        return text # Trả về nguyên gốc nếu độ dài không hợp lý

    # Bảng map sửa lỗi các ký tự dễ nhầm
    # Nhầm Chữ -> Số (Dùng cho 2 ký tự đầu và dãy số cuối)
    dict_char_to_int = {'O': '0', 'D': '0', 'Q': '0', 'I': '1', 'L': '1', 'Z': '2', 'B': '3', 'S': '5', 'G': '6'}
    # Nhầm Số -> Chữ (Dùng cho ký tự thứ 3 - Series)
    dict_int_to_char = {'0': 'O', '1': 'I', '2': 'Z', '3': 'B', '4': 'A', '5': 'S', '6': 'G', '7': 'T', '8': 'B', '9': 'G'}

    text_list = list(text)

    # QUY LUẬT 1: 2 ký tự đầu tiên phải là SỐ (Mã tỉnh)
    for i in range(2):
        if text_list[i] in dict_char_to_int:
            text_list[i] = dict_char_to_int[text_list[i]]

    # QUY LUẬT 2: Ký tự thứ 3 phải là CHỮ (Series)
    # (Chỉ áp dụng nếu biển dài >= 7 ký tự)
    if text_list[2] in dict_int_to_char:
        text_list[2] = dict_int_to_char[text_list[2]]

    # QUY LUẬT 3: Các ký tự từ thứ 4 trở đi phải là SỐ
    for i in range(3, len(text_list)):
        if text_list[i] in dict_char_to_int:
            text_list[i] = dict_char_to_int[text_list[i]]

    # Format lại cho đẹp: XXL-XXXXX
    final_str = "".join(text_list)
    
    # Thêm dấu gạch ngang hoặc chấm để dễ đọc (Tùy chọn)
    # Ví dụ: 30A12345 -> 30A-123.45
    if len(final_str) >= 7:
        prefix = final_str[:3] # 3 ký tự đầu (VD: 30A)
        suffix = final_str[3:] # Phần còn lại (VD: 12345)
        
        if len(suffix) == 5:
            return f"{prefix}-{suffix[:3]}.{suffix[3:]}" # 30A-123.45
        else:
            return f"{prefix}-{suffix}" # 30A-1234
            
    return final_str