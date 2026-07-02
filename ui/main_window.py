"""메인 창: 홈 ↔ 세션 (QStackedWidget) + 관리자 다이얼로그."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from core.appconfig import load_app_config
from core.bgm import Bgm
from core.frame_source import FrameSource
from ui.admin_dialog import AdminDialog
from ui.attract import AttractOverlay
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

        self._bgm = Bgm()
        self._apply_bgm()

        # 어트랙트 모드: 홈에서 일정 시간 입력 없으면 예시 슬라이드쇼로 호객
        self._attract = AttractOverlay(self)
        self._attract.hide()
        self._attract.dismissed.connect(self._reset_idle)
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(self._show_attract)
        QApplication.instance().installEventFilter(self)
        self._reset_idle()

        if fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)

    # ---- 어트랙트 모드 ----
    def _attract_ms(self) -> int:
        try:
            return int(float(load_app_config().get("attractSeconds", 45)) * 1000)
        except (TypeError, ValueError):
            return 45000

    def _reset_idle(self) -> None:
        ms = self._attract_ms()
        if ms > 0:
            self._idle.start(ms)
        else:
            self._idle.stop()

    def _show_attract(self) -> None:
        if self._stack.currentWidget() is self.home and self._attract.has_content():
            self._attract.setGeometry(self.rect())
            self._attract.raise_()
            self._attract.show()
        else:
            self._reset_idle()  # 세션/대결 중 — 나중에 다시

    def eventFilter(self, obj, ev) -> bool:
        t = ev.type()
        if t in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress,
                 QEvent.Type.TouchBegin):
            self._reset_idle()
        return super().eventFilter(obj, ev)

    def resizeEvent(self, e) -> None:
        if self._attract.isVisible():
            self._attract.setGeometry(self.rect())
        super().resizeEvent(e)

    def _apply_bgm(self) -> None:
        if load_app_config().get("bgm", True) and self._bgm.available:
            self._bgm.start()
        else:
            self._bgm.stop()

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
        pin = str(load_app_config().get("adminPin", "4000"))
        if pin:
            from PySide6.QtWidgets import QDialog

            from ui.pin_dialog import PinDialog
            if PinDialog(pin, self).exec() != QDialog.DialogCode.Accepted:
                return
        AdminDialog(self._camera_index, self).exec()
        self.home.refresh()
        self._apply_bgm()  # 관리자에서 BGM 설정이 바뀌었을 수 있음

    def closeEvent(self, e) -> None:
        self._bgm.stop()
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
