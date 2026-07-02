"""Qt 공용 유틸."""

from __future__ import annotations

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
    rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
    h, w = rgb.shape[:2]
    img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(img.copy())
