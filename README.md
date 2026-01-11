# Smart-Parking-Access-System

Hệ thống quản lý bãi đỗ xe thông minh sử dụng công nghệ AI (Computer Vision) để nhận diện phương tiện và đọc biển số xe tự động. Dự án được tối ưu hóa để chạy trên máy tính cá nhân và hỗ trợ thao tác qua điện thoại di động.

## 🚀 Tính năng nổi bật

1.  **Check-in / Check-out tự động:**
    *   Tự động phát hiện xe (Ô tô, Xe máy, Xe buýt, Xe tải) bằng **YOLOv8**.
    *   Tự động cắt ảnh xe và đọc biển số bằng **EasyOCR**.
    *   Hỗ trợ xử lý ảnh nâng cao (CLAHE, Đảo màu) để đọc biển số bị lóa hoặc xe màu trắng.
    *   Kiểm tra định dạng biển số Việt Nam (VD: 30A-123.45).
2.  **Tối ưu hóa hiệu năng:**
    *   **Xử lý trên RAM:** Ảnh chỉ được lưu xuống ổ cứng khi nhận diện thành công và hợp lệ (tránh rác hệ thống).
    *   **GPU Acceleration:** Tự động sử dụng GPU (CUDA) nếu có để tăng tốc độ xử lý.
3.  **Quản lý & Tính phí:**
    *   Tính tiền gửi xe tự động dựa trên thời gian gửi.
    *   Ngăn chặn Check-in trùng lặp.
4.  **Báo cáo & Xuất dữ liệu:**
    *   Xuất báo cáo ra file Excel (`.xlsx`) theo khoảng thời gian.
    *   Hỗ trợ xóa dữ liệu cũ để giải phóng dung lượng.
5.  **Hỗ trợ Mobile (HTTPS):**
    *   Tích hợp sẵn Server HTTPS để trình duyệt điện thoại có thể mở Camera quét mã.

---

## 💻 Yêu cầu hệ thống (System Requirements)

Để hệ thống hoạt động ổn định với các model AI, máy tính cần đáp ứng cấu hình tối thiểu sau:

*   **Hệ điều hành:** Windows 10/11, macOS hoặc Linux.
*   **Python:** Phiên bản **3.9** đến **3.11** (Khuyên dùng 3.10).
*   **RAM:** Tối thiểu **4GB** (Khuyên dùng 8GB trở lên để load model YOLO và EasyOCR mượt mà).
*   **CPU:** Core i5 thế hệ 4 trở lên hoặc tương đương.
*   **GPU (Tùy chọn):** NVIDIA GTX/RTX với CUDA để tăng tốc độ nhận diện (nếu không có sẽ chạy bằng CPU chậm hơn chút).
*   **Dung lượng ổ cứng:** Trống ít nhất 2GB (để lưu thư viện và ảnh chụp xe).
*   **Camera:** Webcam USB hoặc Camera laptop (để test tính năng quét).

---

## ️ Công nghệ sử dụng

*   **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy.
*   **AI/CV:** Ultralytics YOLOv8, EasyOCR, OpenCV, PyTorch.
*   **Database:** SQLite.
*   **Frontend:** HTML/JS thuần (phục vụ qua Python HTTP Server).

---

## ⚙️ Hướng dẫn Cài đặt & Chạy (Từng bước)

Làm theo các bước sau để thiết lập hệ thống từ đầu:

### Bước 1: Tạo môi trường ảo (Virtual Environment)
Mở Terminal (CMD/PowerShell) tại thư mục gốc của dự án và chạy:

```bash
# 1. Tạo môi trường ảo tên là 'venv'
python -m venv venv

# 2. Kích hoạt môi trường
# Trên Windows:
.\venv\Scripts\activate
# Trên Mac/Linux:
source venv/bin/activate
```

### Bước 2: Cài đặt thư viện
Sau khi kích hoạt venv, chạy lệnh sau để tải các thư viện cần thiết:
```bash
pip install -r requirements.txt
```
*(Lưu ý: Nếu máy có Card rời NVIDIA, hãy cài PyTorch bản hỗ trợ CUDA để chạy nhanh hơn)*

### Bước 2: Tạo chứng chỉ SSL (Quan trọng)
Bạn cần tạo 2 file `server.key` và `server.crt` và đặt chúng vào thư mục **`frontend/`**.

Nếu có Git Bash hoặc OpenSSL, chạy lệnh sau:
```bash
openssl req -x509 -newkey rsa:4096 -keyout frontend/server.key -out frontend/server.crt -days 365 -nodes
```
*Lưu ý: Khi chạy lệnh, cứ nhấn Enter để bỏ qua các thông tin khai báo.*

### Bước 3: Khởi chạy hệ thống

**1. Chạy Backend (Terminal 1):**
```bash
cd backend
python run_https.py
```
*Backend sẽ chạy tại: `https://0.0.0.0:8000`*

**2. Chạy Frontend (Terminal 2):**
```bash
cd frontend
python serve_https.py
```
*Frontend sẽ chạy tại: `https://0.0.0.0:5500`*

### Bước 4: Kết nối từ điện thoại
1.  Đảm bảo điện thoại và máy tính dùng chung mạng Wifi.
2.  Tìm địa chỉ IP LAN của máy tính (VD: `192.168.1.10`).
3.  **Quan trọng:** Mở trình duyệt điện thoại, truy cập `https://192.168.1.10:8000/docs` -> Chọn **Nâng cao (Advanced)** -> **Tiếp tục (Proceed)** để chấp nhận chứng chỉ bảo mật của Backend trước.
4.  Sau đó truy cập trang chủ: `https://192.168.1.10:5500/index.html`.

---

## 🔄 Luồng xử lý dữ liệu (Data Flow)

Hệ thống áp dụng chiến lược **"Xử lý trước - Lưu sau"**:

1.  **Nhận ảnh:** Ảnh từ Camera được gửi lên Backend và lưu vào RAM.
2.  **Phân tích AI:**
    *   YOLOv8 phát hiện xe và cắt vùng ảnh xe.
    *   EasyOCR đọc biển số từ ảnh cắt (có áp dụng CLAHE/Threshold để tăng độ nét).
3.  **Kiểm tra Logic:**
    *   Nếu không đọc được biển hoặc biển sai định dạng -> **Hủy bỏ, không lưu ảnh**.
    *   Nếu xe đang trong bãi mà check-in lại -> **Báo lỗi**.
4.  **Lưu trữ:**
    *   Chỉ khi mọi thứ hợp lệ, ảnh mới được ghi vào thư mục `uploads/` và `crops/`.
    *   Thông tin phiên gửi xe được lưu vào Database SQLite.

---

## 💰 Cơ chế tính phí

Phí gửi xe được tính tự động khi Check-out dựa trên thời gian gửi:

| Thời gian gửi | Mức phí |
| :--- | :--- |
| Dưới 4 giờ | 5.000 VNĐ |
| Từ 4h - 12 giờ | 30.000 VNĐ |
| Trên 12 giờ | 50.000 VNĐ |

---

## 📂 Cấu trúc thư mục

```text
Smart-Parking-Access-System/
├── backend/
│   ├── main.py             # API Server chính
│   ├── run_https.py        # Script chạy Backend với SSL
│   ├── yolo_utils.py       # Logic AI (YOLO + EasyOCR + Xử lý ảnh)
│   ├── crud.py             # Các hàm thao tác Database
│   ├── models.py           # Định nghĩa bảng DB
│   ├── database.py         # Cấu hình kết nối DB
│   ├── uploads/            # Chứa ảnh gốc (Tự tạo)
    └── crops/              # Chứa ảnh cắt vùng xe (Tự tạo)
├── frontend/
│   ├── index.html          # Giao diện chính
│   ├── serve_https.py      # Script chạy Web Server với SSL
│   ├── server.key          # Private Key (Bạn cần tạo)
│   └── server.crt          # Certificate (Bạn cần tạo)
└── README.md               # Tài liệu hướng dẫn
```
