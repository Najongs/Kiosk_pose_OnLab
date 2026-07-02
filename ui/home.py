"""홈 화면: 좌측 브랜딩·시작, 우측 코스 카드 + 리더보드 (키오스크 와이드 레이아웃)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.courses import load_courses
from core.leaderboard import top_n

_DIFF_COLOR = {"초급": "#2ee6a6", "중급": "#ffdc40", "고급": "#ff5a6a"}


class _CourseCard(QFrame):
    """난이도 색 스트라이프 + 이름/설명/자세 수를 담은 클릭형 카드."""

    clicked = Signal()

    def __init__(self, c: dict):
        super().__init__()
        color = _DIFF_COLOR.get(c.get("difficulty", ""), "#9aa4bd")
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(110)
        self.setStyleSheet(f"""
            QFrame#card {{
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.09);
                border-left: 5px solid {color};
                border-radius: 16px;
            }}
            QFrame#card:hover {{
                background: rgba(74,168,255,0.10);
                border: 1px solid rgba(74,168,255,0.45);
                border-left: 5px solid {color};
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 16, 14)
        v.setSpacing(6)

        top = QHBoxLayout()
        name = QLabel(c["name"])
        name.setStyleSheet("font-size:21px; font-weight:800; color:#eef2fb;")
        chip = QLabel(c.get("difficulty", "") or "코스")
        chip.setStyleSheet(
            f"color:{color}; background:{color}26; border-radius:10px;"
            "padding:2px 10px; font-size:14px; font-weight:700;")
        top.addWidget(name)
        top.addStretch()
        top.addWidget(chip)
        v.addLayout(top)

        desc = QLabel(c.get("desc", ""))
        desc.setStyleSheet("color:#9aa4bd; font-size:15px;")
        desc.setWordWrap(True)
        v.addWidget(desc)

        meta_txt = f"{len(c['poses'])}개 자세"
        if c.get("shuffle"):
            meta_txt += "  ·  🔀 무작위"
        meta = QLabel(meta_txt)
        meta.setStyleSheet("color:#6f7890; font-size:14px; font-weight:600;")
        v.addWidget(meta)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class HomeWidget(QWidget):
    # name, poses(빈 리스트면 기본 세트)
    startRequested = Signal(str, list)
    versusRequested = Signal()
    adminRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")  # DARK_QSS 의 그라데이션 배경 적용
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QHBoxLayout(self)
        root.setContentsMargins(56, 40, 56, 44)
        root.setSpacing(44)

        # ---- 좌: 브랜딩 + 시작 ----
        left = QVBoxLayout()
        left.setSpacing(14)
        left.addStretch(3)

        badge = QLabel("AI 포즈 코치")
        badge.setStyleSheet(
            "color:#2ee6a6; background:rgba(46,230,166,0.12);"
            "border:1px solid rgba(46,230,166,0.35); border-radius:12px;"
            "padding:4px 14px; font-size:15px; font-weight:700;")
        brow = QHBoxLayout()
        brow.addWidget(badge)
        brow.addStretch()
        left.addLayout(brow)

        title = QLabel("OnLab")
        title.setStyleSheet("font-size:92px; font-weight:900; color:#2ee6a6;"
                            "letter-spacing:2px;")
        sub = QLabel("유연성 테스트")
        sub.setStyleSheet("font-size:34px; font-weight:800; color:#eef2fb;")
        tag = QLabel("카메라 앞에서 안내되는 자세를 따라 하고\n점수를 겨뤄보세요.")
        tag.setStyleSheet("color:#9aa4bd; font-size:18px; line-height:150%;")
        left.addWidget(title)
        left.addWidget(sub)
        left.addWidget(tag)
        left.addSpacing(18)

        self.name = QLineEdit()
        self.name.setPlaceholderText("이름 입력 (선택)")
        self.name.setMaxLength(12)
        self.name.setFixedWidth(340)
        self.name.returnPressed.connect(self._start)
        left.addWidget(self.name)

        start = QPushButton("빠른 시작  ▶")
        start.setObjectName("primary")
        start.setFixedWidth(340)
        start.clicked.connect(self._start)
        versus = QPushButton("⚔  2인 대결")
        versus.setFixedWidth(340)
        versus.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "  stop:0 #ff6ec4, stop:1 #7a5cff); color:#fff; font-weight:800;"
            "  font-size:20px; border:none; border-radius:18px; padding:14px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "  stop:0 #ff85cf, stop:1 #8f74ff); }")
        versus.clicked.connect(self.versusRequested.emit)
        left.addSpacing(4)
        left.addWidget(start)
        left.addWidget(versus)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#ffd27f; font-size:16px;")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        left.addStretch(4)

        foot = QLabel("OnLab Kiosk · AI Pose Estimation")
        foot.setStyleSheet("color:#4d5470; font-size:13px;")
        left.addWidget(foot)

        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(420)
        root.addWidget(lw)

        # ---- 우: 코스 + 리더보드 ----
        right = QVBoxLayout()
        right.setSpacing(12)

        header = QHBoxLayout()
        ct = QLabel("코스 선택")
        ct.setStyleSheet("font-size:26px; font-weight:800;")
        gear = QPushButton("⚙")
        gear.setFixedSize(52, 52)
        gear.setStyleSheet("border-radius:26px; font-size:22px; padding:0;")
        gear.setToolTip("관리자 설정")
        gear.clicked.connect(self.adminRequested.emit)
        header.addWidget(ct)
        header.addStretch()
        header.addWidget(gear)
        right.addLayout(header)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 6, 0)
        grid.setSpacing(14)
        for i, c in enumerate(load_courses()):
            card = _CourseCard(c)
            card.clicked.connect(lambda c=c: self._start_course(c))
            grid.addWidget(card, i // 2, i % 2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(grid_host)
        right.addWidget(scroll, 5)

        lb_title = QLabel("🏆 리더보드")
        lb_title.setStyleSheet("font-size:24px; font-weight:800; margin-top:6px;")
        right.addWidget(lb_title)
        self.lb = QListWidget()
        self.lb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lb.setAlternatingRowColors(True)
        self.lb.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        right.addWidget(self.lb, 4)

        root.addLayout(right, 1)
        self.refresh()

    def _start(self) -> None:
        self.startRequested.emit(self.name.text().strip(), [])

    def _start_course(self, c: dict) -> None:
        poses = list(c["poses"])
        if c.get("shuffle"):
            import random
            random.shuffle(poses)  # 시작할 때마다 새 순서
        self.startRequested.emit(self.name.text().strip(), poses)

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
            rank = medals[i] if i < 3 else f" {i + 1} "
            name = r.get("name") or "익명"
            item = QListWidgetItem(f"{rank}  {name:<14s} {round(r.get('total', 0))}점")
            if i < 3:
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self.lb.addItem(item)
