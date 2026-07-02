"""Qt 공용 유틸."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap

DARK_QSS = """
QWidget { background: #0b0e17; color: #eef2fb;
  font-family: 'Noto Sans KR', sans-serif; font-size: 18px; }
QPushButton { background: #2b3350; color: #eef2fb; border: none;
  border-radius: 12px; padding: 12px 22px; font-weight: 700; }
QPushButton:hover { background: #38426b; }
QPushButton#primary { background: #2ee6a6; color: #05231a; font-size: 22px; }
QPushButton#danger { background: rgba(255,90,106,0.18); color: #ff5a6a; }
QLineEdit, QSpinBox, QDoubleSpinBox { background: rgba(255,255,255,0.06);
  border: 2px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 8px 12px; }
QLineEdit:focus { border-color: #4aa8ff; }
QListWidget { background: rgba(18,22,34,0.7); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px; padding: 6px; }
QCheckBox { spacing: 10px; }
"""


def bgr_to_qpixmap(frame_bgr: np.ndarray) -> QPixmap:
    # Format_BGR888 로 채널 스왑 복사(비쌈)를 생략 — fromImage 가 픽스맵으로 복사함
    frame = np.ascontiguousarray(frame_bgr)
    h, w = frame.shape[:2]
    img = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_BGR888)
    return QPixmap.fromImage(img)


def fit_frame(frame_bgr: np.ndarray, size: tuple[int, int] | None) -> np.ndarray:
    """뷰 크기에 맞게 비율 유지 리사이즈. 워커 스레드에서 호출해 UI 스레드의
    고비용 QPixmap.scaled(Smooth) 를 없앤다. size 가 아직 없으면 원본 그대로."""
    if not size:
        return frame_bgr
    vw, vh = size
    if vw < 16 or vh < 16:
        return frame_bgr
    h, w = frame_bgr.shape[:2]
    s = min(vw / w, vh / h)
    if 0.98 <= s <= 1.0:
        return frame_bgr
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_LINEAR
    return cv2.resize(frame_bgr, (nw, nh), interpolation=interp)
