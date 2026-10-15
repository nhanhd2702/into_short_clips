# Universal AI Shorts & Reels Generator 🎬⚡
> **Tự động cắt video dài thành Shorts / TikTok / Reels chuẩn dọc 9:16 — Hoàn toàn Miễn phí, 100% Chạy Offline (Không tốn tiền API, Không dính Watermark)**

Mã nguồn mở thay thế hoàn hảo cho **Opus Clip, Vidyo.ai, Klap, SubMagic** với khả năng xử lý cả **Video Trò chuyện (Speech/Podcasts)** lẫn **Video Thể thao / Hành động (Sports/Action/Gaming)**.

---

## ✨ Điểm Nổi Bật (Key Features)

- 🎙️ **Chế độ Lời thoại (Speech Mode):** Tự động bóc tách phụ đề bằng `faster-whisper` (tiếng Việt & đa ngôn ngữ), dùng mô hình ngôn ngữ (Ollama `qwen2.5:3b` hoặc Gemini API) phân tích các đoạn mở đầu (hook) kịch tính, tự động bám mặt người nói để crop dọc 9:16.
- 🏸 **Chế độ Thể thao (Sports Mode):** Quét phân tích biểu đồ năng lượng âm thanh (Audio Peak Energy) để tóm gọn các pha cầu giằng co, cú smash, bàn thắng hoặc tiếng reo hò của khán giả. Sử dụng bố cục **Pillarbox Blur 9:16** chuyên nghiệp (toàn cảnh sân đấu ở giữa, nền mờ thẩm mỹ phía trên dưới).
- 🤖 **Chế độ Tự động (Auto Mode):** Tự động kiểm tra giọng nói trong video; nếu không có lời thoại (như trận đấu thể thao), hệ thống tự chuyển sang chế độ phân tích âm thanh cao trào.
- 💻 **100% Offline & Riêng tư:** Chạy hoàn toàn trên máy tính cá nhân bằng CPU/GPU nội bộ, không tải video lên đám mây, không giới hạn số lượng video.
- 🚀 **Cài đặt & Chạy 1-Click:** Có sẵn các script tự động `setup.bat`, `run.bat` cho Windows và hỗ trợ cả Docker.

---

## 🚀 Cài Đặt Nhanh (1-Click Setup)

### Cách 1: Chạy trực tiếp trên Windows (Khuyên dùng)

1. Tải hoặc clone repository về máy:
   ```bash
   git clone https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator.git
   cd AI-Youtube-Shorts-Generator
   ```

2. Chạy file cài đặt tự động:
   * **Cách đơn giản:** Nhấp đúp chuột vào file **`setup.bat`** (hoặc mở PowerShell gõ `.\setup.ps1`).
   * Script sẽ tự động:
     - Tạo môi trường ảo Python `.venv`.
     - Cài đặt toàn bộ thư viện AI cần thiết.
     - Tải Ollama Portable và kéo mô hình `qwen2.5:3b` về máy để chạy offline.
     - Tạo file cấu hình `.env` mặc định.

### Cách 2: Chạy bằng Docker
```bash
docker compose build
```

---

## 🎯 Hướng Dẫn Sử Dụng (Quick Start)

### 1. Dùng Script tiện ích 1-Click (`run.bat` / `run.ps1`)

* **Cắt video trò chuyện / Podcast (Theo lời thoại):**
  ```powershell
  .\run.ps1 "D:\Videos\podcast.mp4" 3 "speech"
  ```
* **Cắt video Thể thao / Cầu lông / Bóng đá (Theo âm lượng hò reo & đập cầu):**
  ```powershell
  .\run.ps1 "D:\Videos\badminton_match.mov" 10 "sports" "9:16" 45
  ```
* **Chế độ Tự động nhận diện (Mặc định):**
  ```powershell
  .\run.ps1 "D:\Videos\any_video.mp4" 3
  ```
*(Nếu dùng Command Prompt CMD, gõ tương tự: `run.bat "video.mp4" 3 auto`)*

---

### 2. Dùng dòng lệnh Python chi tiết

```bash
# Cắt 3 clip từ link YouTube hoặc file local:
.\.venv\Scripts\python.exe main.py "https://www.youtube.com/watch?v=VIDEO_ID" --num-clips 3

# Cắt 10 clip thể thao độ dài 45s mỗi clip:
.\.venv\Scripts\python.exe main.py "D:\Videos\match.mp4" --type sports --num-clips 10 --duration 45

# Cắt video trò chuyện ép ngôn ngữ tiếng Việt:
.\.venv\Scripts\python.exe main.py "talkshow.mp4" --type speech --language vi --num-clips 5
```

---

## ⚙️ Tùy Chọn Cấu Hình (`.env`)

Mở file `.env` để tùy biến theo nhu cầu:

```env
# 1. Chọn nguồn trí tuệ nhân tạo:
#    - "ollama": Chạy 100% Offline trên máy (Mặc định, không cần key)
#    - "gemini": Dùng Google Gemini API (Miễn phí hạn mức lớn, siêu nhanh)
#    - "openai": Dùng OpenAI API
LLM_PROVIDER=ollama

# Cấu hình Ollama Offline:
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b

# Cấu hình Gemini Cloud (tùy chọn):
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Cấu hình Whisper:
LOCAL_WHISPER_MODEL=base
LOCAL_WHISPER_DEVICE=cpu

# Thư mục lưu kết quả:
LOCAL_OUTPUT_DIR=output
```

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
AI-Youtube-Shorts-Generator/
├── shorts_generator/          # Nhân mã nguồn chính của AI Pipeline
│   ├── sports.py             # Engine bóc tách highlight thể thao (Audio Energy Peaks)
│   ├── pipeline.py           # Engine điều phối chung
│   ├── highlights.py         # Prompt LLM phân tích virality & hooks
│   └── local/
│       ├── transcriber.py    # Phiên âm nhanh qua faster-whisper (CPU int8)
│       ├── clipper.py        # Cắt clip & bám mặt người nói qua OpenCV
│       └── llm.py            # Kết nối Ollama, Gemini, OpenAI
├── main.py                   # Điểm khởi chạy CLI chính
├── setup.bat / setup.ps1     # Script cài đặt môi trường 1-click
├── run.bat / run.ps1         # Script chạy cắt Shorts 1-click
├── requirements-local.txt    # Danh sách thư viện đã được kiểm thử ổn định
├── Dockerfile                # File đóng gói Docker
├── docker-compose.yml        # Cấu hình khởi chạy qua Docker
└── output/                   # Thư mục chứa các video Shorts xuất ra
```

---

## 🛠️ Khắc Phục Lỗi Thường Gặp (Troubleshooting)

1. **Lỗi `av` hoặc `ffmpeg`:**  
   Kho dữ liệu đã được ghim phiên bản `av<14` và `opencv-python<5` để đảm bảo độ tương thích 100% với Windows.
2. **Lỗi Windows File Lock:**  
   Hệ thống đã tích hợp cơ chế tự động giải phóng bộ nhớ `gc.collect()` và retry an toàn khi xóa file tạm.
3. **Mô hình AI trên máy không có GPU rời:**  
   Hệ thống được tối ưu hóa đặc biệt để chạy mượt mà ngay trên **CPU thông thường (Intel Core i5/i7) với 8GB-16GB RAM** thông qua `faster-whisper-base (int8)` và mô hình `qwen2.5:3b`.

---

## 📜 Giấy Phép (License)
Dự án được phân phối dưới giấy phép **MIT License**. Bạn có thể tự do sử dụng, chỉnh sửa và tích hợp vào các dự án thương mại hoặc cá nhân.
