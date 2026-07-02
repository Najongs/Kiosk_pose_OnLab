"""어트랙트 모드(호객 대기 화면).

홈 화면에서 일정 시간 입력이 없으면 전체를 덮고 동작 예시 이미지를
슬라이드쇼로 돌리며 "도전해 보세요" 문구를 보여준다. 아무 곳이나
터치/클릭하면 닫히고 홈으로 돌아간다.
"""

from __future__ import annotations

import glob
import json
import os
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
_EXAMPLES_DIR = os.path.join(_CONFIG_DIR, "examples")
_POSES_DIR = os.path.join(_CONFIG_DIR, "poses")
_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _display_names() -> dict[str, str]:
    """slug → 한글 표시명 (config/poses/*.json)."""
    names: dict[str, str] = {}
    for p in glob.glob(os.path.join(_POSES_DIR, "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            names[os.path.splitext(os.path.basename(p))[0]] = d.get(
                "display_name", "")
        except (OSError, json.JSONDecodeError):
            pass
    return names


class AttractOverlay(QWidget):
    dismissed = Signal()

    def __init__(self, parent=None, interval_ms: int = 2600):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background:#05070d;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 50, 40, 40)
        title = QLabel("유연성 테스트에 도전해 보세요!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:52px; font-weight:900; color:#2ee6a6;"
                            "background:transparent;")
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setStyleSheet("background:transparent;")
        self._caption = QLabel("")
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setStyleSheet("font-size:24px; color:#9aa4bd;"
                                    "background:transparent;")
        hint = QLabel("▶ 화면을 터치하면 시작됩니다")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size:28px; font-weight:700; color:#eef2fb;"
                           "background:rgba(46,230,166,0.14); border-radius:16px;"
                           "padding:14px;")
        root.addWidget(title)
        root.addWidget(self._img, 1)
        root.addWidget(self._caption)
        root.addSpacing(14)
        root.addWidget(hint)

        # 예시 이미지 수집 (연속동작 _N 스텝 포함, 파일명 순)
        self._paths = sorted(
            p for ext in _EXTS
            for p in glob.glob(os.path.join(_EXAMPLES_DIR, f"*{ext}")))
        self._names = _display_names()
        self._idx = 0
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._next)

    def has_content(self) -> bool:
        return bool(self._paths)

    def showEvent(self, e) -> None:
        self._next()
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e) -> None:
        self._timer.stop()
        super().hideEvent(e)

    def _next(self) -> None:
        if not self._paths:
            return
        path = self._paths[self._idx % len(self._paths)]
        self._idx += 1
        pix = QPixmap(path)
        if pix.isNull():
            return
        avail = self._img.size()
        if avail.width() > 32 and avail.height() > 32:
            pix = pix.scaled(avail, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        self._img.setPixmap(pix)
        slug = os.path.splitext(os.path.basename(path))[0]
        base = re.sub(r"_\d+$", "", slug)  # 연속동작 스텝(_1, _2) 접미 제거
        self._caption.setText(self._names.get(base) or base.replace("_", " "))

    def mousePressEvent(self, e) -> None:
        self.hide()
        self.dismissed.emit()
