"""메인 창: 홈 ↔ 세션 (QStackedWidget) + 관리자 다이얼로그."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from core.appconfig import load_app_config
from core.frame_source import FrameSource
from ui.admin_dialog import AdminDialog
from ui.home import HomeWidget
from ui.qtutil import DARK_QSS
from ui.session_view import SessionView
from ui.versus_view import VersusView


class MainWindow(QMainWindow):
    def __init__(self, source_factory: Callable[[], FrameSource],
                 camera_index: int = 0, fullscreen: bool = True):
        super().__init__()
        self.setWindowTitle("OnLab — 스트레칭/유연성 테스트")
        self.setStyleSheet(DARK_QSS)
        self._source_factory = source_factory
        self._camera_index = camera_index

        self._stack = QStackedWidget()
        self.home = HomeWidget()
        self.session = SessionView()
        self.versus = VersusView()
        self._stack.addWidget(self.home)
        self._stack.addWidget(self.session)
        self._stack.addWidget(self.versus)
        self.setCentralWidget(self._stack)

        self.home.startRequested.connect(self._start_session)
        self.home.versusRequested.connect(self._start_versus)
        self.home.adminRequested.connect(self._open_admin)
        self.session.exitRequested.connect(self._go_home)
        self.versus.exitRequested.connect(self._go_home)

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)

    def _start_session(self, name: str, poses: list | None = None) -> None:
        cfg = load_app_config()
        if poses:
            cfg = dict(cfg)
            cfg["poseSet"] = list(poses)
        self.home.set_status("")
        try:
            # 카메라 열기/모델 로드는 세션 뷰의 워커 스레드에서 수행(클릭 즉시 전환)
            self.session.begin(name, cfg, self._source_factory)
        except Exception as e:
            self.home.set_status(f"시작 실패: {e}")
            return
        self._stack.setCurrentWidget(self.session)

    def _start_versus(self) -> None:
        cfg = load_app_config()
        self.home.set_status("")
        try:
            self.versus.begin(cfg, self._source_factory)
        except Exception as e:
            self.home.set_status(f"시작 실패: {e}")
            return
        self._stack.setCurrentWidget(self.versus)

    def _go_home(self) -> None:
        self.home.refresh()
        self._stack.setCurrentWidget(self.home)

    def _open_admin(self) -> None:
        AdminDialog(self._camera_index, self).exec()
        self.home.refresh()

    def closeEvent(self, e) -> None:
        self.session.stop()
        self.versus.stop()
        from core.warm import close_all
        close_all()
        super().closeEvent(e)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        # Esc: 세션/대결 중이면 홈으로, 홈에서는 종료. (일반 글자키 Q 로는 종료 안 함)
        if e.key() == Qt.Key.Key_Escape:
            cur = self._stack.currentWidget()
            if cur is self.session:
                self.session._exit()
            elif cur is self.versus:
                self.versus._exit()
            else:
                self.close()
        elif e.key() in (Qt.Key.Key_F, Qt.Key.Key_F11):
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
