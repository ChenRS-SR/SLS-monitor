"""Probe potential UVC (USB Video Class) thermal camera devices.

If your Type-C 热成像相机实际上是一个标准UVC设备，它不会通过串口输出像素，而是作为视频摄像头出现。
此脚本：
 1. 枚举前 N (默认 6) 个摄像头索引
 2. 尝试打开，抓取若干帧，统计分辨率、是否为单通道(灰度)或多通道
 3. 第一帧保存为 PNG (可选)

用法 (PowerShell):
  python probe_uvc.py
  python probe_uvc.py --max-index 10 --frames 20 --save-first

若发现某索引持续返回帧且分辨率稳定(例如 256x192, 160x120, 384x288)，即可对接到解析/温度映射流程。

依赖: opencv-python (cv2)
"""
from __future__ import annotations
import cv2
import time
import argparse
from pathlib import Path


def probe_index(idx: int, frames: int, delay: float, save_first: bool, out_dir: Path):
    print(f"\n=== Trying camera index {idx} ===")
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # CAP_DSHOW for Windows to speed open
    if not cap.isOpened():
        print("[FAIL] cannot open")
        return
    ok_frames = 0
    first_saved = False
    start = time.time()
    while ok_frames < frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.05)
            continue
        ok_frames += 1
        shape = frame.shape
        channels = 1 if len(shape) == 2 else shape[2]
        print(f"[{idx}] frame#{ok_frames} shape={shape} channels={channels} min={frame.min()} max={frame.max()} dtype={frame.dtype}")
        if save_first and not first_saved:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"camera{idx}_first.png"
            cv2.imwrite(str(out_path), frame)
            print(f"Saved first frame to {out_path}")
            first_saved = True
        time.sleep(delay)
    elapsed = time.time() - start
    print(f"[{idx}] captured {ok_frames} frames in {elapsed:.2f}s -> {ok_frames/elapsed:.1f} FPS")
    cap.release()


def main():
    ap = argparse.ArgumentParser(description="Probe UVC thermal camera candidates")
    ap.add_argument('--max-index', type=int, default=6, help='Max camera index (exclusive) to try, starting at 0')
    ap.add_argument('--frames', type=int, default=10, help='Frames per opened camera index')
    ap.add_argument('--delay', type=float, default=0.05, help='Delay between reads to avoid flooding')
    ap.add_argument('--save-first', action='store_true', help='Save the first successful frame per camera index')
    ap.add_argument('--out', type=str, default='uvc_probe_output', help='Directory for saved frames')
    args = ap.parse_args()

    out_dir = Path(args.out)

    for i in range(args.max_index):
        probe_index(i, args.frames, args.delay, args.save_first, out_dir)


if __name__ == '__main__':
    main()
