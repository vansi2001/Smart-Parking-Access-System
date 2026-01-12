# Smart-Parking-Access-System

Hệ thống quản lý bãi đỗ xe thông minh sử dụng công nghệ AI (Computer Vision) để nhận diện phương tiện và đọc biển số xe tự động. Dự án bao gồm đầy đủ tính năng từ nhận diện, tính phí, quản lý danh sách ưu tiên (Whitelist) đến báo cáo thống kê.

## 🚀 Tính năng nổi bật

1.  **Check-in / Check-out tự động:**
    *   Tự động phát hiện xe và đọc biển số bằng **YOLOv8** & **EasyOCR**.
    *   Hỗ trợ xử lý ảnh nâng cao (CLAHE, Đảo màu) để đọc biển số khó.
    *   **Hiệu ứng quét Laser** trực quan trên giao diện.
    *   **Sửa nhanh:** Cho phép bảo vệ sửa lại biển số ngay lập tức nếu AI nhận diện sai.
    *   **Xác nhận xe vãng lai:** Cảnh báo khi xe lạ vào bãi, yêu cầu xác nhận trước khi mở cổng.

2.  **Quản lý Whitelist (Xe ưu tiên):**
    *   Quản lý danh sách xe cư dân/nhân viên.
    *   **Miễn phí gửi xe** tự động cho xe trong Whitelist.
    *   **Ra/Vào Nhanh:** Danh sách chọn nhanh trên giao diện để cho xe quen vào không cần quét camera.
    *   Nhập liệu hàng loạt từ file **CSV**.

3.  **Trang Quản trị (Admin Dashboard):**
    *   Giao diện quản trị chuyên nghiệp (Login bảo mật).
    *   **Tra cứu thông minh:** Tìm kiếm xe theo biển số (gần đúng), xem lịch sử ra vào.
    *   **Quản lý dữ liệu:** Sửa hoặc Xóa các lượt gửi xe sai lệch.
    *   **Báo cáo:** Xuất file Excel (`.xlsx`) thống kê doanh thu và lượt xe.

4.  **Tối ưu hóa & Bảo mật:**
    *   **Xử lý trên RAM:** Không lưu ảnh rác nếu nhận diện thất bại.
    *   **HTTPS:** Hỗ trợ chạy trên trình duyệt điện thoại di động.

---

## 💻 Yêu cầu hệ thống (System Requirements)

*   **Hệ điều hành:** Windows 10/11, macOS hoặc Linux.
*   **Python:** 3.9 - 3.11.
*   **RAM:** Tối thiểu 4GB (Khuyên dùng 8GB).
*   **Camera:** Webcam hoặc Camera điện thoại (qua IP Webcam).

---

## ️ Công nghệ sử dụng

*   **Backend:** Python, FastAPI, Uvicorn, SQLAlchemy.
*   **AI/CV:** Ultralytics YOLOv8, EasyOCR, OpenCV, PyTorch.
*   **Frontend:** HTML5, CSS3, JavaScript (Vanilla).
*   **Database:** SQLite.

---

## ⚙️ Hướng dẫn Cài đặt & Chạy

### Bước 1: Cài đặt môi trường
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

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
