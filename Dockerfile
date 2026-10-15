FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Cài đặt FFmpeg và các thư viện hệ thống cần thiết cho OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt dependencies Python
COPY requirements.txt requirements-local.txt ./
RUN pip install --no-cache-dir -r requirements-local.txt

# Copy source code
COPY . .

# Tạo thư mục đầu vào/đầu ra
RUN mkdir -p input output

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
