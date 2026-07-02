"""홈 화면: 타이틀 + 이름 입력 + 시작 + 리더보드 + 관리자 진입."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from core.courses import load_courses
from core.leaderboard import top_n

_DIFF_COLOR = {"초급": "#2ee6a6", "중급": "#ffdc40", "고급": "#ff5a6a"}


class HomeWidget(QWidget):
    # name, poses(빈 리스트면 기본 세트)
    startRequested = Signal(str, list)
    versusRequested = Signal()
    adminRequested = Signal()

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(60, 40, 60, 60)
        root.setSpacing(18)

        top = QHBoxLayout()
        top.addStretch()
        gear = QPushButton("⚙")
        gear.setFixedSize(52, 52)
        gear.setStyleSheet("border-radius:26px; font-size:24px;")
        gear.clicked.connect(self.adminRequested.emit)
        top.addWidget(gear)
        root.addLayout(top)

        title = QLabel("OnLab")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 88px; font-weight: 900; color: #2ee6a6;")
        sub = QLabel("유연성 테스트")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 30px; font-weight: 700; color: #eef2fb;")
        tag = QLabel("카메라 앞에서 안내되는 자세를 따라 하고 점수를 겨뤄보세요.")
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag.setStyleSheet("color:#9aa4bd; font-size:18px;")
        root.addWidget(title)
        root.addWidget(sub)
        root.addWidget(tag)

        row = QHBoxLayout()
        row.addStretch()
        self.name = QLineEdit()
        self.name.setPlaceholderText("이름 입력 (선택)")
        self.name.setMaxLength(12)
        self.name.setFixedWidth(320)
        self.name.returnPressed.connect(self._start)
        start = QPushButton("빠른 시작")
        start.setObjectName("primary")
        start.clicked.connect(self._start)
        versus = QPushButton("⚔ 2인 대결")
        versus.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                             "stop:0 #ff6ec4, stop:1 #7a5cff); color:#fff; font-weight:800;")
        versus.clicked.connect(self.versusRequested.emit)
        row.addWidget(self.name)
        row.addWidget(start)
        row.addWidget(versus)
        row.addStretch()
        root.addSpacing(10)
        root.addLayout(row)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color:#ffd27f;")
        root.addWidget(self.status)

        # 코스 선택
        ct = QLabel("코스 선택")
        ct.setStyleSheet("font-size:22px; font-weight:800; margin-top:8px;")
        ct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(ct)
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, c in enumerate(load_courses()):
            grid.addWidget(self._course_card(c), i // 3, i % 3)
        root.addLayout(grid)

        lb_title = QLabel("🏆 리더보드")
        lb_title.setStyleSheet("font-size:24px; font-weight:800;")
        lb_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addSpacing(14)
        root.addWidget(lb_title)
        self.lb = QListWidget()
        self.lb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(self.lb, 1)

        self.refresh()

    def _course_card(self, c: dict) -> QPushButton:
        color = _DIFF_COLOR.get(c.get("difficulty", ""), "#9aa4bd")
        btn = QPushButton(f"{c['name']}\n{c.get('difficulty','')} · {len(c['poses'])}개 자세")
        btn.setToolTip(c.get("desc", ""))
        btn.setMinimumHeight(84)
        btn.setStyleSheet(
            f"text-align:left; padding:14px 16px; font-size:18px; font-weight:700;"
            f"background: rgba(74,168,255,0.10); border:1px solid {color}55; border-radius:14px;")
        btn.clicked.connect(lambda: self.startRequested.emit(self.name.text().strip(), list(c["poses"])))
        return btn

    def _start(self) -> None:
        self.startRequested.emit(self.name.text().strip(), [])

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def refresh(self) -> None:
        self.lb.clear()
        rows = top_n(10)
        if not rows:
            self.lb.addItem("아직 기록이 없어요. 첫 도전자가 되어보세요!")
            return
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            rank = medals[i] if i < 3 else str(i + 1)
            name = r.get("name") or "익명"
            item = QListWidgetItem(f"{rank}   {name}    —    {round(r.get('total', 0))}점")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lb.addItem(item)
