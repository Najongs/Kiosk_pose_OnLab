"""Qt 공용 유틸."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap

DARK_QSS = """
QWidget { background: transparent; color: #eef2fb;
  font-family: 'Pretendard', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
  font-size: 18px; }
QMainWindow, QDialog, QWidget#screen {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #0c1020, stop:0.55 #0a0d18, stop:1 #101527); }

QPushButton { background: rgba(255,255,255,0.07); color: #eef2fb;
  border: 1px solid rgba(255,255,255,0.10); border-radius: 14px;
  padding: 12px 24px; font-weight: 700; }
QPushButton:hover { background: rgba(255,255,255,0.13);
  border-color: rgba(74,168,255,0.55); }
QPushButton:pressed { background: rgba(255,255,255,0.05); }
QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #2ee6a6, stop:1 #19b8d8); color: #04241c; font-size: 22px;
  border: none; padding: 16px 34px; border-radius: 18px; }
QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #45f0b6, stop:1 #2cc9e8); }
QPushButton#danger { background: rgba(255,90,106,0.12); color: #ff8291;
  border: 1px solid rgba(255,90,106,0.35); }
QPushButton#danger:hover { background: rgba(255,90,106,0.22); }

QLineEdit, QSpinBox, QDoubleSpinBox { background: rgba(255,255,255,0.06);
  border: 2px solid rgba(255,255,255,0.12); border-radius: 14px;
  padding: 10px 16px; selection-background-color: #2ee6a6;
  selection-color: #04241c; }
QLineEdit:focus, QDoubleSpinBox:focus { border-color: #2ee6a6;
  background: rgba(46,230,166,0.05); }

QListWidget { background: rgba(255,255,255,0.035);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px; padding: 8px; outline: none;
  alternate-background-color: rgba(255,255,255,0.04); }
QListWidget::item { border-radius: 12px; padding: 10px 14px; margin: 3px 4px;
  background: transparent; }
QListWidget::item:alternate { background: rgba(255,255,255,0.04); }
QListWidget::item:selected { background: rgba(46,230,166,0.12); color: #eef2fb; }

QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 22px; height: 22px; border-radius: 7px;
  border: 2px solid rgba(255,255,255,0.25); background: rgba(255,255,255,0.04); }
QCheckBox::indicator:checked { background: #2ee6a6; border-color: #2ee6a6;
  image: none; }

QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.18);
  border-radius: 5px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.30); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #1a2136; color: #eef2fb;
  border: 1px solid rgba(255,255,255,0.15); padding: 6px 10px; }
"""


def bgr_to_qpixmap(frame_bgr: np.ndarray) -> QPixmap:
    # Format_BGR888 로 채널 스왑 복사(비쌈)를 생략 — fromImage 가 픽스맵으로 복사함
    frame = np.ascontiguousarray(frame_bgr)
    h, w = frame.shape[:2]
    img = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_BGR888)
    return QPixmap.fromImage(img)


def draw_fps(frame_bgr: np.ndarray, disp_ts, infer_ts) -> None:
    """좌상단에 표시/추론 FPS 진단 오버레이 (ASCII — cv2 로 빠르게)."""
    def rate(ts) -> float:
        if len(ts) >= 2 and ts[-1] > ts[0]:
            return (len(ts) - 1) / (ts[-1] - ts[0])
        return 0.0
    txt = f"{rate(disp_ts):4.1f} fps | infer {rate(infer_ts):4.1f}"
    cv2.putText(frame_bgr, txt, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame_bgr, txt, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (140, 255, 170), 1, cv2.LINE_AA)


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
