import cv2
import os
from ultralytics import YOLO
import easyocr
import numpy as np
import re

# Load model YOLOv8 nano (sẽ tự động tải file yolov8n.pt về thư mục hiện tại nếu chưa có)
# Model này nhận diện được 80 loại đối tượng trong bộ dữ liệu COCO
model = YOLO("yolov8n.pt")

# Khởi tạo EasyOCR (chỉ tải model lần đầu chạy)
reader = easyocr.Reader(['en'], gpu=False) # gpu=True nếu máy có NVIDIA GPU

# Danh sách class ID của các loại xe trong COCO dataset
# 2: car, 3: motorcycle, 5: bus, 7: truck
VEHICLE_CLASSES = [2, 3, 5, 7]

def detect_and_crop_vehicle(image_path: str, output_dir: str) -> str:
    """
    Nhận diện xe trong ảnh và cắt ảnh xe đó ra.
    Trả về đường dẫn file ảnh đã cắt (hoặc None nếu không tìm thấy xe).
    """
    # Đọc ảnh
    img = cv2.imread(image_path)
    if img is None:
        return None

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
        
        # Tạo tên file output
        base_name = os.path.basename(image_path)
        crop_name = f"crop_{base_name}"
        crop_path = os.path.join(output_dir, crop_name)
        
        # Lưu ảnh cắt
        cv2.imwrite(crop_path, crop_img)
        return crop_path
    
    return None

def read_plate_text(image_path: str) -> str:
    """
    Đọc văn bản từ file ảnh sử dụng EasyOCR.
    Sử dụng OpenCV để xử lý ảnh trước khi đưa vào OCR.
    """
    if not image_path or not os.path.exists(image_path):
        return None
        
    # Đọc ảnh và chuyển sang Grayscale để OCR tốt hơn
    img = cv2.imread(image_path)
    if img is None:
        return None

    # 1. Xử lý ảnh (Preprocessing)
    # Phóng to ảnh lên 2 lần để OCR dễ đọc các chi tiết nhỏ
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Khử nhiễu nhẹ
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    
    # 2. Đọc text (detail=0 chỉ lấy nội dung text)
    # allowlist: Giới hạn chỉ đọc chữ và số để giảm nhiễu
    results = reader.readtext(gray, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.')
    
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
    # Biển số thường có từ 7 đến 9 ký tự (bao gồm cả mã tỉnh, series và số)
    if len(text) < 7 or len(text) > 9:
        return text # Trả về nguyên gốc nếu độ dài không hợp lý

    # Bảng map sửa lỗi các ký tự dễ nhầm
    # Nhầm Chữ -> Số (Dùng cho 2 ký tự đầu và dãy số cuối)
    dict_char_to_int = {'O': '0', 'D': '0', 'I': '1', 'L': '1', 'Z': '2', 'B': '8', 'S': '5', 'G': '6'}
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