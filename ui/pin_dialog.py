"""관리자 진입 PIN 다이얼로그 — 키오스크(터치) 친화 숫자 패드.

키보드 숫자/백스페이스 입력도 지원. PIN 은 config/app_config.json 의
"adminPin" (기본 "4000") 으로 변경할 수 있다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QPushButton, QVBoxLayout


class PinDialog(QDialog):
    def __init__(self, pin: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관리자 인증")
        self.setModal(True)
        self.setFixedSize(360, 500)
        self._pin = pin
        self._entered = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        title = QLabel("관리자 비밀번호")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:24px; font-weight:800;")
        self._dots = QLabel("")
        self._dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dots.setStyleSheet("font-size:36px; letter-spacing:10px; color:#2ee6a6;")
        self._msg = QLabel(" ")
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg.setStyleSheet("color:#ff5a6a;")
        root.addWidget(title)
        root.addWidget(self._dots)
        root.addWidget(self._msg)

        grid = QGridLayout()
        grid.setSpacing(10)
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "←", "0", "취소"]
        for i, k in enumerate(keys):
            btn = QPushButton(k)
            btn.setMinimumSize(92, 68)
            btn.setStyleSheet("font-size:24px;")
            if k == "←":
                btn.clicked.connect(self._back)
            elif k == "취소":
                btn.clicked.connect(self.reject)
            else:
                btn.clicked.connect(lambda _=False, d=k: self._digit(d))
            grid.addWidget(btn, i // 3, i % 3)
        root.addLayout(grid)
        self._refresh()

    def _refresh(self) -> None:
        n = len(self._pin)
        self._dots.setText("●" * len(self._entered) + "○" * max(0, n - len(self._entered)))

    def _digit(self, d: str) -> None:
        if len(self._entered) >= len(self._pin):
            return
        self._entered += d
        self._msg.setText(" ")
        self._refresh()
        if len(self._entered) == len(self._pin):
            if self._entered == self._pin:
                self.accept()
            else:
                self._entered = ""
                self._refresh()
                self._msg.setText("비밀번호가 틀렸습니다")

    def _back(self) -> None:
        self._entered = self._entered[:-1]
        self._msg.setText(" ")
        self._refresh()

    def keyPressEvent(self, e) -> None:
        if Qt.Key.Key_0 <= e.key() <= Qt.Key.Key_9:
            self._digit(chr(e.key()))
        elif e.key() == Qt.Key.Key_Backspace:
            self._back()
        else:
            super().keyPressEvent(e)
