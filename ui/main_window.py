"""메인 창: 홈 ↔ 게임 뷰(레지스트리 기반, 지연 생성) + 관리자 다이얼로그."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget

from core.appconfig import load_app_config
from core.bgm import Bgm
from core.frame_source import FrameSource
from ui.admin_dialog import AdminDialog
from ui.attract import AttractOverlay
from ui.game_registry import GAMES
from ui.home import HomeWidget
from ui.qtutil import DARK_QSS


class MainWindow(QMainWindow):
    def __init__(self, source_factory: Callable[[], FrameSource],
                 camera_index: int = 0, fullscreen: bool = True):
        super().__init__()
        self.setWindowTitle("OnLab — AI 체험 게임")
        self.setStyleSheet(DARK_QSS)
        self._source_factory = source_factory
        self._camera_index = camera_index

        self._stack = QStackedWidget()
        self.home = HomeWidget()  # 어트랙트 모드가 currentWidget() is home 을 검사
        self._stack.addWidget(self.home)
        self._views: dict[str, QWidget] = {}  # game_id → 뷰 (선택 시 지연 생성)
        self.setCentralWidget(self._stack)

        self.home.gameSelected.connect(self._start_game)
        self.home.adminRequested.connect(self._open_admin)

        self._bgm = Bgm()
        self._apply_bgm()

        # 어트랙트 모드: 홈에서 일정 시간 입력 없으면 라이브 미러로 호객
        # (카메라에 비치는 행인 스켈레톤 실시간 표시, 실패 시 슬라이드쇼 폴백)
        self._attract = AttractOverlay(self, source_factory=source_factory)
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

    def _start_game(self, game_id: str, params: dict) -> None:
        gdef = GAMES.get(game_id)
        if gdef is None:
            self.home.set_status(f"알 수 없는 게임: {game_id}")
            return
        self.home.set_status("")
        try:
            # 뷰 지연 생성(import 포함)도 실패할 수 있으므로 가드 안에서.
            # 카메라 열기/모델 로드는 뷰의 워커 스레드에서 수행(클릭 즉시 전환)
            view = self._views.get(game_id)
            if view is None:
                view = gdef.make_view()
                view.exitRequested.connect(self._go_home)
                self._stack.addWidget(view)
                self._views[game_id] = view
            gdef.start(view, params, load_app_config(), self._source_factory)
        except Exception as e:
            self.home.set_status(f"시작 실패: {e}")
            return
        self._stack.setCurrentWidget(view)

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
        for view in self._views.values():
            view.stop()
        from core.warm import close_all
        close_all()
        super().closeEvent(e)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        # Esc: 게임 중이면 홈으로, 홈에서는 종료. (일반 글자키 Q 로는 종료 안 함)
        if e.key() == Qt.Key.Key_Escape:
            cur = self._stack.currentWidget()
            if cur is self.home:
                self.close()
            else:
                cur._exit()  # 모든 게임 뷰가 제공 (stop + exitRequested)
        elif e.key() in (Qt.Key.Key_F, Qt.Key.Key_F11):
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
