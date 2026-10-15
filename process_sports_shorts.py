import os
import sys
import subprocess
import numpy as np
import wave

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VIDEO_PATH = r"D:\04_Personal_Family\Photos_Galleries\Videos\[29-09-2019](MS-QF) Dac Nhan vs Tan Tran (Nội bộ UIT 2019).MOV"
OUT_DIR = r"D:\04_Personal_Family\Photos_Galleries\Videos\Shorts_DacNhan_vs_TanTran"
LOCAL_COPY_DIR = r"D:\02_Study_Knowledge\AI_Engineering\AI_Projects\AI\Github Collection\Top Skill\AI-Youtube-Shorts-Generator\output\DacNhan_vs_TanTran"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(LOCAL_COPY_DIR, exist_ok=True)

# 1. Trích xuất waveform âm thanh để tìm các pha cầu kịch tính nhất (Audio Energy Peaks)
temp_wav = "temp_analysis_audio.wav"
print(">>> [1/3] Đang phân tích âm thanh toàn bộ trận đấu (39.5 phút) để tìm 10 pha cầu kịch tính nhất...")
subprocess.run([
    "ffmpeg", "-y", "-i", VIDEO_PATH,
    "-vn", "-ac", "1", "-ar", "8000",
    temp_wav
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

with wave.open(temp_wav, "rb") as wf:
    rate = wf.getframerate()
    n_frames = wf.getnframes()
    raw = wf.readframes(n_frames)
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32)

if os.path.exists(temp_wav):
    os.remove(temp_wav)

# Tính năng lượng RMS theo cửa sổ 2 giây
win = 2 * rate
step = rate
energies = []
timestamps = []
for i in range(0, len(audio) - win, step):
    chunk = audio[i : i + win]
    rms = np.sqrt(np.mean(chunk**2))
    energies.append(rms)
    timestamps.append(i / rate)

energies = np.array(energies)
timestamps = np.array(timestamps)

# Chọn top 10 đỉnh âm lượng cách nhau ít nhất 90 giây
sorted_idx = np.argsort(energies)[::-1]
picked = []
for idx in sorted_idx:
    t = timestamps[idx]
    if all(abs(t - p) > 90 for p in picked):
        picked.append(t)
    if len(picked) >= 10:
        break

picked.sort()

# Danh sách 10 clip (độ dài 45s mỗi clip, bắt đầu 35s trước cú ghi điểm/hò reo và 10s sau đó)
clips = []
for i, t in enumerate(picked, 1):
    start = max(0.0, t - 35.0)
    end = min(len(audio)/rate, start + 45.0)
    dur = end - start
    m, s = int(t // 60), int(t % 60)
    clips.append({
        "index": i,
        "peak_time": t,
        "peak_str": f"{m:02d}:{s:02d}",
        "start": start,
        "end": end,
        "duration": dur
    })

print("\n>>> [2/3] Đã xác định thành công danh sách 10 pha cầu đỉnh cao:")
for c in clips:
    print(f"  Short #{c['index']:02d} | Điểm cao trào: {c['peak_str']} | Khung thời gian: {c['start']:.1f}s -> {c['end']:.1f}s (Thời lượng: {c['duration']:.1f}s)")

# 2. Render 10 clip Shorts dọc 9:16 với hiệu ứng nền mờ (Pillarbox Blur) giữ trọn vẹn toàn bộ sân cầu
print("\n>>> [3/3] Bắt đầu cắt và xuất 10 video Shorts chuẩn dọc 9:16 (1080x1920)...")
for c in clips:
    out_filename = f"Short_{c['index']:02d}_Peak_{c['peak_str'].replace(':', 'm')}s.mp4"
    out_file = os.path.join(OUT_DIR, out_filename)
    local_file = os.path.join(LOCAL_COPY_DIR, out_filename)
    
    print(f"\n--- Đang render Short #{c['index']:02d}/{len(clips)}: {out_filename} ({c['duration']:.0f}s) ---")
    
    # Filter 9:16 giữ toàn cảnh sân cầu ở giữa + nền mờ phía trên dưới
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        "[0:v]scale=1080:-1[fg];"
        "[bg][fg]overlay=0:(H-h)/2"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{c['start']:.3f}",
        "-t", f"{c['duration']:.3f}",
        "-i", VIDEO_PATH,
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-preset", "faster",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "128k",
        "-threads", "0",
        out_file
    ]
    
    subprocess.run(cmd, check=True)
    
    # Copy sang thư mục output của repo để tiện xem
    import shutil
    shutil.copy2(out_file, local_file)
    print(f"  => Hoàn thành: {out_file}")

print("\n=======================================================")
print(f"TẤT CẢ 10 FILE SHORT ĐÃ ĐƯỢC XUẤT THÀNH CÔNG VÀO:")
print(f"1. Thư mục chính: {OUT_DIR}")
print(f"2. Thư mục dự án: {LOCAL_COPY_DIR}")
print("=======================================================")
