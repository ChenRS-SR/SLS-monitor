import numpy as np
import cv2
import glob

# --- 配置参数 ---
chessboard_size = (7, 9)  # 内部角点数量 (width, height) 对应8x10的方格
square_size = 1.0         # 标定板每个方格的实际物理尺寸（单位：毫米）。这里设为1，因为Z坐标用层厚表示了，实际大小可通过层厚缩放。
layer_heights = np.array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])  # 10个图层的Z坐标（毫米）

def main():
    objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
    objp *= square_size  # 将棋盘格点乘上物理尺寸
    print(f"objp shape: {objp.shape}")
    print(f"objp: {objp}")

if __name__ == "__main__":
    main()