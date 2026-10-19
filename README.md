# into_short_clips 🎬⚡
> **Universal AI Video Shorts & Reels Generator — 100% Offline, Local & Miễn Phí (Không tốn tiền API, Không dính Watermark)**

[![GitHub](https://img.shields.io/badge/GitHub-into__short__clips-blue?logo=github)](https://github.com/nhanhd2702/into_short_clips)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-orange)]()
[![Ollama](https://img.shields.io/badge/Ollama-qwen2.5:3b%20Offline-purple?logo=ollama)](https://ollama.com/)

**into_short_clips** là giải pháp mã nguồn mở thay thế hoàn hảo cho **Opus Clip, Vidyo.ai, Klap, SubMagic**, cho phép tự động chuyển đổi các video dài (Podcasts, Talkshow, Video thể thao, Cầu lông, Bóng đá, Gaming) thành các clip ngắn **Shorts / TikTok / Reels chuẩn dọc 9:16 (Full HD 1080x1920)** hoàn toàn tự động ngay trên máy tính của bạn.

---

## ✨ Điểm Nổi Bật (Key Features)

- 🎙️ **Chế độ Lời thoại (Speech Mode):** Tự động bóc tách phụ đề bằng `faster-whisper` (tiếng Việt & đa ngôn ngữ), dùng mô hình ngôn ngữ (Ollama `qwen2.5:3b` cục bộ hoặc Google Gemini) phân tích tìm các câu mở đầu (hook) kịch tính và các đoạn cao trào chia sẻ sâu sắc.
- 🏸 **Chế độ Thể thao & Hành động (Sports Mode):** Quét phân tích biểu đồ năng lượng âm thanh (Audio Energy Peaks) để tóm gọn các pha cầu kịch tính, smash, bàn thắng hoặc tiếng reo hò khán giả.
- 🤖 **Chế độ Tự động (Auto Mode):** Tự động phát hiện giọng nói trong video; nếu video không có thoại (trận đấu thể thao, highlight hành động), hệ thống tự chuyển sang chế độ quét âm lượng đỉnh.
- 📱 **Định dạng chuẩn dọc 9:16 Full HD (1080x1920):**
  - **Pillarbox Blur thẩm mỹ (Mặc định):** Giữ trọn 100% khung hình gốc ở giữa, hai dải trên/dưới được phủ mờ đồng điệu màu sắc (`boxblur` mượt mà). Không bao giờ bị cắt xén phụ đề hay logo.
  - **Face Tracking Crop:** Tự động nhận diện và bám sát mặt nhân vật bằng OpenCV.
- 🎞️ **Chuẩn nén quốc tế H.264 (AVC1) + YUV420p:** Tương thích 100% trên Windows Media Player, QuickTime (macOS), iPhone, Android, CapCut, Premiere, TikTok, Shorts.
- 💻 **100% Offline & Bảo mật tuyệt đối:** Chạy trực tiếp trên CPU/GPU nội bộ của máy tính, không tải video lên bất kỳ server bên thứ ba nào, không giới hạn thời lượng hay số lượng video.
- 🚀 **1-Click Setup & Run:** Tích hợp sẵn bộ công cụ chạy tức thì cho cả **Windows** (`setup.bat`, `run.bat`, `setup.ps1`, `run.ps1`) và **macOS / Linux** (`setup.sh`, `run.sh`).

---

## 🖥️ Hướng Dẫn Cài Đặt 1-Click (Setup Guide)

Clone kho mã nguồn về máy:
```bash
git clone https://github.com/nhanhd2702/into_short_clips.git
cd into_short_clips
```

### 1. Dành cho Windows 10 / 11

#### Cách 1: Chạy file cài đặt tự động (Khuyên dùng)
* Nhấp đúp chuột vào file **`setup.bat`** (hoặc mở PowerShell trong thư mục dự án và gõ `.\setup.ps1`).
* Script sẽ tự động thực hiện từ A đến Z:
  1. Tạo môi trường ảo Python `.venv`.
  2. Cài đặt các thư viện AI ổn định (`faster-whisper`, `opencv-python`, `av<14`, `yt-dlp`...).
  3. Tự động kiểm tra và tải bản **FFmpeg Portable** nếu máy chưa có.
  4. Tự động kiểm tra và tải **Ollama Portable** + tải model `qwen2.5:3b` chạy ngầm.
  5. Tạo sẵn file `.env` chuẩn 100% Offline.

---

### 2. Dành cho macOS (Apple Silicon M1/M2/M3/M4 & Intel)

#### Bước 1: Chuẩn bị công cụ cơ bản
Mở terminal và đảm bảo máy đã có [Homebrew](https://brew.sh) cùng Python 3.10+:
```bash
# Cài Homebrew nếu chưa có:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Cài đặt FFmpeg và Ollama:
brew install ffmpeg ollama python@3.12
```

#### Bước 2: Chạy script 1-Click Setup
```bash
chmod +x setup.sh run.sh
./setup.sh
```
Script sẽ tự khởi tạo virtual environment `.venv`, cài đặt thư viện cần thiết, khởi động Ollama và kéo model `qwen2.5:3b`.

---

### 3. Dành cho Docker (Linux / Cloud Server)
```bash
docker compose build
```

---

## 🎯 Hướng Dẫn Sử Dụng Nhanh (Quick Start)

### 1. Trên Windows

Sử dụng tiện ích `run.bat` hoặc PowerShell `.\run.ps1`:

* **Cắt video trò chuyện / Podcast (chuẩn dọc 1080x1920 Pillarbox Blur):**
  ```powershell
  .\run.ps1 "D:\Videos\podcast.mp4" 3 speech
  ```
* **Cắt video Thể thao / Cầu lông / Bóng đá (theo năng lượng âm thanh):**
  ```powershell
  .\run.ps1 "D:\Videos\badminton_match.mov" 10 sports
  ```
* **Cắt video từ link YouTube trực tiếp:**
  ```powershell
  .\run.ps1 "https://www.youtube.com/watch?v=ZCl5AUp36GA" 5 speech
  ```
* **Chế độ tự động nhận diện (Speech -> Sports fallback):**
  ```powershell
  .\run.ps1 "video.mp4" 3
  ```
*(Người dùng Command Prompt CMD chỉ cần gõ tương tự: `run.bat "video.mp4" 3 speech`)*

---

### 2. Trên macOS

Sử dụng script `./run.sh`:

* **Cắt video Podcast / Phỏng vấn:**
  ```bash
  ./run.sh "podcast.mp4" 3 speech
  ```
* **Cắt video Thể thao (10 clip, mỗi clip 45s):**
  ```bash
  ./run.sh "match.mov" --type sports --num-clips 10 --duration 45
  ```
* **Cắt trực tiếp từ link YouTube:**
  ```bash
  ./run.sh "https://www.youtube.com/watch?v=ZCl5AUp36GA" --num-clips 5
  ```
* **Chọn kiểu crop bám mặt nhân vật (Face-tracking):**
  ```bash
  ./run.sh "interview.mp4" --num-clips 3 --crop-style face
  ```

---

### 3. Gọi trực tiếp bằng dòng lệnh Python (`main.py`)

```bash
# Windows:
.\.venv\Scripts\python.exe main.py "video.mp4" --type speech --num-clips 5 --crop-style blur

# macOS / Linux:
source .venv/bin/activate
python main.py "video.mp4" --type speech --num-clips 5 --crop-style blur
```

#### Bảng tham số chi tiết của `main.py`:
| Tham số | Mặc định | Tùy chọn | Mô tả |
|---|---|---|---|
| `url` | *(Bắt buộc)* | File path hoặc link YouTube | Đường dẫn video local (`.mp4`, `.mov`, `.mkv`) hoặc URL YouTube |
| `--type` | `auto` | `auto`, `speech`, `sports` | `speech`: dùng Whisper + LLM; `sports`: dùng Audio Peaks; `auto`: tự chọn |
| `--num-clips` | `3` | Số nguyên (ví dụ: `5`, `10`) | Số lượng clip Shorts cần cắt |
| `--crop-style` | `blur` | `blur`, `face` | `blur`: 1080x1920 Pillarbox Blur thẩm mỹ; `face`: OpenCV bám sát khuôn mặt |
| `--aspect-ratio`| `9:16` | `9:16`, `1:1` | Tỷ lệ khung hình xuất ra |
| `--duration` | `45.0` | Số thực (giây) | Thời lượng mỗi clip khi chạy chế độ thể thao (`sports`) |
| `--language` | `None` | `vi`, `en`, `ja`... | Ngôn ngữ phiên âm Whisper (để trống để tự động nhận diện) |
| `--output-dir` | `output` | Thư mục bất kỳ | Thư mục lưu các file video Shorts hoàn thiện |

---

## ⚙️ Cấu Hình Nâng Cao (`.env`)

Tệp `.env` được tạo sẵn khi chạy `setup`. Bạn có thể tùy biến:

```env
# 1. Chọn LLM Provider:
#    - "ollama": Chạy 100% Offline trên máy (Mặc định, Miễn phí, Không cần Key)
#    - "gemini": Dùng Google Gemini API (Miễn phí từ aistudio.google.com, siêu nhanh)
#    - "openai": Dùng OpenAI API
LLM_PROVIDER=ollama

# Cấu hình Ollama Offline:
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b

# Cấu hình Google Gemini Cloud (Tùy chọn nếu muốn tăng tốc độ tối đa):
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Cấu hình Whisper (Local STT):
# Các size: tiny, base, small, medium, large-v3 (Khuyên dùng 'base' hoặc 'small' trên CPU)
LOCAL_WHISPER_MODEL=base
LOCAL_WHISPER_DEVICE=auto

# Thư mục lưu video đầu ra:
LOCAL_OUTPUT_DIR=output
```

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
into_short_clips/
├── shorts_generator/          # Nhân mã nguồn chính của AI Pipeline
│   ├── sports.py             # Engine cắt highlight thể thao (Audio Energy Peaks)
│   ├── pipeline.py           # Bộ điều phối quy trình tự động
│   ├── highlights.py         # Prompt LLM phân tích virality & hook moments
│   └── local/
│       ├── transcriber.py    # Phiên âm nhanh qua faster-whisper (CPU int8 / GPU)
│       ├── clipper.py        # Xuất video 1080x1920 Pillarbox Blur & OpenCV Face Crop
│       └── llm.py            # Client kết nối Ollama (offline), Gemini, OpenAI
├── main.py                   # Điểm khởi chạy CLI chính
├── setup.bat / setup.ps1     # Script cài đặt môi trường 1-click cho Windows
├── run.bat / run.ps1         # Script chạy cắt Shorts 1-click cho Windows
├── setup.sh                  # Script cài đặt 1-click cho macOS / Linux
├── run.sh                    # Script chạy 1-click cho macOS / Linux
├── requirements-local.txt    # Danh sách thư viện Python chuẩn đã kiểm thử
├── Dockerfile                # File cấu hình Docker
├── docker-compose.yml        # Cấu hình triển khai nhanh Docker
└── output/                   # Thư mục chứa các video Shorts xuất ra
```

---

## 🛠️ Câu Hỏi Thường Gặp & Khắc Phục Lỗi (FAQ & Troubleshooting)

### 1. Video mở lên trên Windows chỉ có tiếng mà không có hình?
* **Đã được giải quyết triệt để:** Dự án sử dụng bộ mã hóa chuẩn quốc tế **H.264 (`avc1`)** với định dạng màu `yuv420p` và cờ `+faststart`. Video phát mượt mà trên tất cả trình phát: Windows Media Player, QuickTime, Movies & TV, Chrome, VLC.

### 2. Máy tính không có card đồ họa rời (GPU) có chạy được không?
* **Hoàn toàn mượt mà!** Pipeline được tinh chỉnh tối ưu hóa chạy trực tiếp trên **CPU thông thường (Intel Core i3/i5/i7, AMD Ryzen hoặc Apple M-series)** với 8GB-16GB RAM:
  - Whisper chạy ở chế độ lượng tử hóa `int8` (tiết kiệm 70% RAM).
  - LLM Ollama `qwen2.5:3b` chỉ chiếm ~1.8GB RAM và phản hồi trong vài giây.

### 3. Phụ đề có bị cắt cụt hai bên khi chuyển sang video dọc 9:16 không?
* Chế độ mặc định **Pillarbox Blur (1080x1920)** giữ nguyên 100% chiều ngang video gốc ở giữa, hai dải trên dưới được làm mờ thẩm mỹ, đảm bảo không bao giờ bị che khuất phụ đề hay logo.

### 4. Lỗi phân quyền khi chạy script trên macOS / Linux?
* Mở terminal và cấp quyền thực thi:
  ```bash
  chmod +x setup.sh run.sh
  ```

---

## 📜 Giấy Phép (License)
Dự án được phân phối dưới giấy phép **MIT License**. Bạn được tự do sử dụng, chỉnh sửa và tích hợp vào các dự án thương mại hoặc cá nhân.
