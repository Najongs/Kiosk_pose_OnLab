"""홈 화면: 좌측 브랜딩·시작, 우측 게임 선택 카드 + 리더보드.

우측 패널은 2페이지: [게임 선택] ↔ [코스 선택](스트레칭 전용 하위 페이지).
게임 시작은 gameSelected(game_id, params) 하나로 MainWindow 에 전달된다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from core.courses import load_courses
from core.leaderboard import top_n
from ui.game_registry import BOARD_TABS, REGISTRY

_DIFF_COLOR = {"초급": "#2ee6a6", "중급": "#ffdc40", "고급": "#ff5a6a"}
_DIFF_EN = {"초급": "Easy", "중급": "Medium", "고급": "Hard"}


def _bi(kr: str, en_: str, size: int = 15) -> str:
    """한국어 + 작은 영어 병기 rich text — 외국인 방문객용 보조 표기."""
    return (f'{kr} &nbsp;<span style="font-size:{size}px; font-weight:600;'
            f' color:#8a94ad;">{en_}</span>')


def _glow(widget, color: str, blur: int = 28, alpha: int = 120,
          dy: int = 4) -> None:
    """위젯 뒤에 액센트색 네온 글로우를 깐다 (QSS 로는 불가한 연출)."""
    eff = QGraphicsDropShadowEffect(widget)
    c = QColor(color)
    c.setAlpha(alpha)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(c)
    widget.setGraphicsEffect(eff)


class _Card(QFrame):
    """색 스트라이프 + 제목/설명을 담은 클릭형 카드 (게임/코스 공용 베이스)."""

    clicked = Signal()

    def __init__(self, accent: str):
        super().__init__()
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(110)
        self.setStyleSheet(f"""
            QFrame#card {{
                background: rgba(255,255,255,0.045);
                border: 1px solid rgba(255,255,255,0.09);
                border-left: 5px solid {accent};
                border-radius: 16px;
            }}
            QFrame#card:hover {{
                background: rgba(74,168,255,0.10);
                border: 1px solid rgba(74,168,255,0.45);
                border-left: 5px solid {accent};
            }}
            QLabel {{ background: transparent; border: none; }}
        """)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class _GameCard(_Card):
    """게임 선택 카드: 이모지 + 제목 + 설명."""

    def __init__(self, title: str, subtitle: str, emoji: str, accent: str,
                 title_en: str = "", subtitle_en: str = ""):
        super().__init__(accent)
        _glow(self, accent, blur=26, alpha=60, dy=6)
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 14, 16, 14)
        h.setSpacing(14)
        icon = QLabel(emoji)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(64, 64)
        icon.setStyleSheet(
            f"font-size:34px; background:{accent}1e; border-radius:32px;"
            f"border:1px solid {accent}55;")
        h.addWidget(icon)
        v = QVBoxLayout()
        v.setSpacing(6)
        # 제목 옆 영어 병기(작게·연하게) — 외국인도 이해, 디자인은 유지
        name = QLabel(title if not title_en else (
            f'{title} &nbsp;<span style="font-size:14px; font-weight:600;'
            f' color:#8a94ad;">{title_en}</span>'))
        name.setTextFormat(Qt.TextFormat.RichText)
        name.setWordWrap(True)  # 영어 병기로 카드 최소폭이 커지지 않게 (좁으면 줄바꿈)
        name.setStyleSheet("font-size:22px; font-weight:800; color:#eef2fb;")
        desc = QLabel(subtitle if not subtitle_en else (
            f'{subtitle}<br><span style="font-size:12px; color:#6f7890;">'
            f'{subtitle_en}</span>'))
        desc.setTextFormat(Qt.TextFormat.RichText)
        desc.setStyleSheet("color:#9aa4bd; font-size:15px;")
        desc.setWordWrap(True)
        v.addWidget(name)
        v.addWidget(desc)
        h.addLayout(v)
        h.addStretch()
        play = QLabel("▶")
        play.setStyleSheet(f"color:{accent}; font-size:22px; font-weight:900;")
        h.addWidget(play)


class _CourseCard(_Card):
    """난이도 색 스트라이프 + 이름/설명/자세 수를 담은 클릭형 카드."""

    def __init__(self, c: dict):
        super().__init__(_DIFF_COLOR.get(c.get("difficulty", ""), "#9aa4bd"))
        color = _DIFF_COLOR.get(c.get("difficulty", ""), "#9aa4bd")
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 14, 16, 14)
        v.setSpacing(6)

        top = QHBoxLayout()
        name = QLabel(c["name"])
        name.setStyleSheet("font-size:21px; font-weight:800; color:#eef2fb;")
        diff = c.get("difficulty", "")
        chip = QLabel(f"{diff} {_DIFF_EN[diff]}" if diff in _DIFF_EN
                      else (diff or "코스"))
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

        n = len(c["poses"])
        meta_txt = f"{n}개 자세 · {n} poses"
        if c.get("shuffle"):
            meta_txt += "  ·  🔀 무작위 random"
        meta = QLabel(meta_txt)
        meta.setStyleSheet("color:#6f7890; font-size:14px; font-weight:600;")
        v.addWidget(meta)


class HomeWidget(QWidget):
    # (game_id, params) — params: {"name": str, "poses": list(스트레칭 전용)}
    gameSelected = Signal(str, dict)
    adminRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("screen")  # DARK_QSS 의 그라데이션 배경 적용
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._lb_game = "stretch"  # 리더보드 탭 선택 상태
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
        _glow(title, "#2ee6a6", blur=44, alpha=150, dy=0)
        sub = QLabel('AI 체험 게임 &nbsp;<span style="font-size:19px;'
                     ' font-weight:600; color:#8a94ad;">AI Motion Games</span>')
        sub.setTextFormat(Qt.TextFormat.RichText)
        sub.setStyleSheet("font-size:34px; font-weight:800; color:#eef2fb;")
        tag = QLabel("카메라가 몸의 움직임을 인식해요.<br>"
                     "게임을 고르고 점수를 겨뤄보세요.<br>"
                     '<span style="font-size:14px; color:#6f7890;">'
                     "The camera tracks your moves — pick a game and beat the"
                     " scores.</span>")
        tag.setTextFormat(Qt.TextFormat.RichText)
        tag.setStyleSheet("color:#9aa4bd; font-size:18px; line-height:150%;")
        left.addWidget(title)
        left.addWidget(sub)
        left.addWidget(tag)
        left.addSpacing(18)

        self.name = QLineEdit()
        self.name.setPlaceholderText("이름 입력 · Name (선택)")
        self.name.setMaxLength(12)
        self.name.setFixedWidth(340)
        self.name.returnPressed.connect(self._start)
        left.addWidget(self.name)

        start = QPushButton("빠른 시작 · Quick Start  ▶")
        start.setObjectName("primary")
        start.setFixedWidth(340)
        start.setToolTip("기본 스트레칭 코스로 바로 시작 / Start the default course")
        start.clicked.connect(self._start)
        _glow(start, "#2ee6a6", blur=36, alpha=110, dy=6)
        left.addSpacing(4)
        left.addWidget(start)

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

        # ---- 우: 게임/코스 선택 (2페이지) + 리더보드 ----
        right = QVBoxLayout()
        right.setSpacing(12)

        header = QHBoxLayout()
        self._panel_title = QLabel(_bi("게임 선택", "Choose a Game"))
        self._panel_title.setTextFormat(Qt.TextFormat.RichText)
        self._panel_title.setStyleSheet("font-size:26px; font-weight:800;")
        self._back_btn = QPushButton("← 게임 선택 · Games")
        self._back_btn.setStyleSheet("font-size:16px; padding:8px 14px;")
        self._back_btn.clicked.connect(self._show_games)
        self._back_btn.hide()
        gear = QPushButton("⚙")
        gear.setFixedSize(52, 52)
        gear.setStyleSheet("border-radius:26px; font-size:22px; padding:0;")
        gear.setToolTip("관리자 설정")
        gear.clicked.connect(self.adminRequested.emit)
        header.addWidget(self._panel_title)
        header.addStretch()
        header.addWidget(self._back_btn)
        header.addWidget(gear)
        right.addLayout(header)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._build_game_page())    # 0: 게임 카드
        self._pages.addWidget(self._build_course_page())  # 1: 코스 카드
        right.addWidget(self._pages, 5)

        lb_head = QHBoxLayout()
        lb_title = QLabel('🏆 리더보드 &nbsp;<span style="font-size:15px;'
                          ' font-weight:600; color:#8a94ad;">Leaderboard</span>')
        lb_title.setTextFormat(Qt.TextFormat.RichText)
        lb_title.setStyleSheet("font-size:24px; font-weight:800; margin-top:6px;")
        lb_head.addWidget(lb_title)
        lb_head.addSpacing(10)
        self._lb_tabs: dict[str, QPushButton] = {}
        for gid, label in BOARD_TABS:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setStyleSheet(
                "QPushButton { font-size:14px; padding:5px 12px; border-radius:12px; }"
                "QPushButton:checked { background:rgba(46,230,166,0.18);"
                "  border:1px solid rgba(46,230,166,0.5); color:#2ee6a6; }")
            b.clicked.connect(lambda _=False, g=gid: self._select_board(g))
            self._lb_tabs[gid] = b
            lb_head.addWidget(b)
        lb_head.addStretch()
        right.addLayout(lb_head)

        self.lb = QListWidget()
        self.lb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lb.setAlternatingRowColors(True)
        self.lb.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        right.addWidget(self.lb, 4)

        root.addLayout(right, 1)
        self.refresh()

    # ---- 우측 페이지 구성 ----
    def _card_grid(self) -> tuple[QScrollArea, QGridLayout]:
        host = QWidget()
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 6, 0)
        grid.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(host)
        return scroll, grid

    def _build_game_page(self) -> QWidget:
        scroll, grid = self._card_grid()
        for i, g in enumerate(REGISTRY):
            card = _GameCard(g.title, g.subtitle, g.emoji, g.accent,
                             g.title_en, g.subtitle_en)
            if g.id == "stretch":
                card.clicked.connect(self._show_courses)
            else:
                card.clicked.connect(lambda gid=g.id: self._start_game(gid))
            grid.addWidget(card, i // 2, i % 2)
        grid.setRowStretch(grid.rowCount(), 1)
        return scroll

    def _build_course_page(self) -> QWidget:
        scroll, grid = self._card_grid()
        for i, c in enumerate(load_courses()):
            card = _CourseCard(c)
            card.clicked.connect(lambda c=c: self._start_course(c))
            grid.addWidget(card, i // 2, i % 2)
        grid.setRowStretch(grid.rowCount(), 1)
        return scroll

    def _show_courses(self) -> None:
        self._pages.setCurrentIndex(1)
        self._panel_title.setText(_bi("코스 선택", "Choose a Course"))
        self._back_btn.show()

    def _show_games(self) -> None:
        self._pages.setCurrentIndex(0)
        self._panel_title.setText(_bi("게임 선택", "Choose a Game"))
        self._back_btn.hide()

    # ---- 시작 ----
    def _params(self) -> dict:
        return {"name": self.name.text().strip()}

    def _start(self) -> None:
        """빠른 시작: 기본 스트레칭 세트."""
        self.gameSelected.emit("stretch", {**self._params(), "poses": []})

    def _start_game(self, game_id: str) -> None:
        self.gameSelected.emit(game_id, self._params())

    def _start_course(self, c: dict) -> None:
        poses = list(c["poses"])
        if c.get("shuffle"):
            import random
            random.shuffle(poses)  # 시작할 때마다 새 순서
        self.gameSelected.emit("stretch", {**self._params(), "poses": poses})

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    # ---- 리더보드 ----
    def _select_board(self, game_id: str) -> None:
        self._lb_game = game_id
        self.refresh()

    def refresh(self) -> None:
        for gid, b in self._lb_tabs.items():
            b.setChecked(gid == self._lb_game)
        self.lb.clear()
        rows = top_n(10, game=self._lb_game)
        if not rows:
            self.lb.addItem("아직 기록이 없어요. 첫 도전자가 되어보세요!"
                            "  ·  No records yet — be the first!")
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
