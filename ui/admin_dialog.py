"""관리자 화면: 설정 편집 + 자세 세트 + 목표 자세 참조 캡처 + 초기화."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from core.appconfig import load_app_config, reset_app_config, save_app_config
from core.leaderboard import clear as clear_leaderboard
from core.pose_def import list_poses, load_pose
from core.refs import clear_ref, has_ref, normalize_pose, set_ref


class AdminDialog(QDialog):
    def __init__(self, camera_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관리자 설정")
        self.resize(560, 720)
        self._camera_index = camera_index
        cfg = load_app_config()

        # 자세가 많아져도 잘리지 않도록 본문은 스크롤 영역에, 하단 버튼은 고정
        outer = QVBoxLayout(self)
        outer.addWidget(_h1("관리자 설정"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        root = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        form = QFormLayout()
        self.pass_spin = QDoubleSpinBox()
        self.pass_spin.setRange(50, 100)
        self.pass_spin.setValue(cfg["passAccuracy"])
        self.count_spin = QDoubleSpinBox()
        self.count_spin.setRange(0, 10)
        self.count_spin.setValue(cfg["countdownSeconds"])
        self.result_spin = QDoubleSpinBox()
        self.result_spin.setRange(0, 10)
        self.result_spin.setValue(cfg["resultSeconds"])
        self.hold_chk = QCheckBox("유지시간 오버라이드")
        self.hold_spin = QDoubleSpinBox()
        self.hold_spin.setRange(0.5, 15)
        self.hold_spin.setSingleStep(0.5)
        ho = cfg["holdSecondsOverride"]
        self.hold_chk.setChecked(ho is not None)
        self.hold_spin.setValue(ho if ho is not None else 3.0)
        self.hold_spin.setEnabled(ho is not None)
        self.hold_chk.toggled.connect(self.hold_spin.setEnabled)
        self.sound_chk = QCheckBox("효과음")
        self.sound_chk.setChecked(cfg["sound"])
        self.voice_chk = QCheckBox("음성 안내 (espeak-ng 필요)")
        self.voice_chk.setChecked(cfg["voice"])
        self.bgm_chk = QCheckBox("배경음악 (assets/bgm 폴더에 음악 파일)")
        self.bgm_chk.setChecked(bool(cfg.get("bgm", True)))
        self.fps_chk = QCheckBox("FPS 표시 (진단용)")
        self.fps_chk.setChecked(bool(cfg.get("showFps", False)))

        form.addRow("합격 정확도(%)", self.pass_spin)
        form.addRow("카운트다운(초)", self.count_spin)
        form.addRow("결과 표시(초)", self.result_spin)
        hrow = QHBoxLayout()
        hrow.addWidget(self.hold_chk)
        hrow.addWidget(self.hold_spin)
        form.addRow(_wrap(hrow))
        form.addRow(self.sound_chk)
        form.addRow(self.voice_chk)
        form.addRow(self.bgm_chk)
        form.addRow(self.fps_chk)
        root.addLayout(form)

        root.addWidget(_h2("자세 세트 (체크한 순서대로 진행)"))
        self.pose_checks: list[QCheckBox] = []
        self._defs = [load_pose(n) for n in list_poses()]
        set_names = cfg["poseSet"]
        ordered = [d for n in set_names for d in self._defs if d.name == n]
        ordered += [d for d in self._defs if d.name not in set_names]
        for d in ordered:
            row = QHBoxLayout()
            chk = QCheckBox(d.display_name)
            chk.setChecked(d.name in set_names)
            chk.setProperty("pose", d.name)
            self.pose_checks.append(chk)
            tag = QLabel("가이드 있음" if has_ref(d.name) else "가이드 없음")
            tag.setStyleSheet(
                "color:#2ee6a6;" if has_ref(d.name) else "color:#9aa4bd;")
            row.addWidget(chk)
            row.addStretch()
            row.addWidget(tag)
            root.addWidget(_wrap(row))

        root.addWidget(_h2("목표 자세 참조 캡처"))
        caprow = QHBoxLayout()
        self.cap_sel = QComboBox()
        for d in self._defs:
            self.cap_sel.addItem(d.display_name, d.name)
        cap_btn = QPushButton("카메라로 캡처")
        cap_btn.clicked.connect(self._open_capture)
        caprow.addWidget(self.cap_sel)
        caprow.addWidget(cap_btn)
        root.addWidget(_wrap(caprow))

        root.addStretch()
        foot = QHBoxLayout()
        clr = QPushButton("리더보드 초기화")
        clr.setObjectName("danger")
        clr.clicked.connect(self._clear_lb)
        rst = QPushButton("설정 초기화")
        rst.setObjectName("danger")
        rst.clicked.connect(self._reset_cfg)
        cam = QPushButton("카메라 재탐색")
        cam.clicked.connect(self._rescan_camera)
        foot.addWidget(cam)
        close = QPushButton("저장 후 닫기")
        close.setObjectName("primary")
        close.clicked.connect(self._save_close)
        foot.addWidget(clr)
        foot.addWidget(rst)
        foot.addStretch()
        foot.addWidget(close)
        outer.addLayout(foot)

    def _collect(self) -> dict:
        cfg = load_app_config()
        pose_set = [c.property("pose") for c in self.pose_checks if c.isChecked()]
        cfg.update({
            "passAccuracy": self.pass_spin.value(),
            "countdownSeconds": self.count_spin.value(),
            "resultSeconds": self.result_spin.value(),
            "holdSecondsOverride": self.hold_spin.value() if self.hold_chk.isChecked() else None,
            "sound": self.sound_chk.isChecked(),
            "voice": self.voice_chk.isChecked(),
            "bgm": self.bgm_chk.isChecked(),
            "showFps": self.fps_chk.isChecked(),
        })
        if pose_set:
            cfg["poseSet"] = pose_set
        return cfg

    def _save_close(self) -> None:
        save_app_config(self._collect())
        self.accept()

    def _clear_lb(self) -> None:
        if QMessageBox.question(self, "확인", "리더보드를 초기화할까요?") == QMessageBox.StandardButton.Yes:
            clear_leaderboard()

    def _reset_cfg(self) -> None:
        if QMessageBox.question(self, "확인", "설정을 기본값으로 되돌릴까요?") == QMessageBox.StandardButton.Yes:
            reset_app_config()
            from core.frame_source import clear_camera_cache
            clear_camera_cache()
            self.reject()

    def _rescan_camera(self) -> None:
        from core.frame_source import clear_camera_cache
        clear_camera_cache()
        QMessageBox.information(
            self, "완료",
            "저장된 카메라 설정을 지웠습니다.\n다음 세션 시작 시 최적 해상도를 다시 측정합니다.")

    def _open_capture(self) -> None:
        pose = self.cap_sel.currentData()
        display = self.cap_sel.currentText()
        dlg = CaptureDialog(pose, display, self._camera_index, self)
        dlg.exec()


class CaptureDialog(QDialog):
    """카메라로 이상적 자세를 잡고 캡처 → 참조 스켈레톤 저장."""

    def __init__(self, pose: str, display: str, camera_index: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"참조 캡처 — {display}")
        self.resize(720, 640)
        self._pose = pose
        self._last_primary = None

        root = QVBoxLayout(self)
        self._label = QLabel("카메라 시작 중…")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setMinimumSize(640, 480)
        root.addWidget(self._label, 1)
        row = QHBoxLayout()
        self._shot = QPushButton("캡처")
        self._shot.setObjectName("primary")
        self._shot.setEnabled(False)
        self._shot.clicked.connect(self._capture)
        cancel = QPushButton("닫기")
        cancel.clicked.connect(self.close)
        row.addWidget(self._shot)
        row.addStretch()
        row.addWidget(cancel)
        root.addLayout(row)

        self._engine = None
        self._source = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        QTimer.singleShot(0, lambda: self._start(camera_index))

    def _start(self, index: int) -> None:
        try:
            from core.frame_source import CameraSource
            from core.tracker import PrimarySubjectTracker
            from core.warm import get_estimator
            self._source = CameraSource(index)
            self._estimator = get_estimator(num_poses=1)  # 공유 모델 재사용
            self._tracker = PrimarySubjectTracker()
            self._engine = True
            self._timer.start(33)
        except Exception as e:
            self._label.setText(f"카메라 오류: {e}")

    def _tick(self) -> None:
        from core.drawing import draw_skeleton
        from ui.qtutil import bgr_to_qpixmap
        frame = self._source.read()
        if frame is None:
            return
        poses = self._estimator.estimate(frame)
        primary = self._tracker.update(poses)
        self._last_primary = primary
        if primary is not None:
            draw_skeleton(frame, primary)
        self._shot.setEnabled(primary is not None)
        self._label.setPixmap(bgr_to_qpixmap(frame).scaled(
            self._label.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def _capture(self) -> None:
        if self._last_primary is None:
            return
        set_ref(self._pose, normalize_pose(self._last_primary))
        QMessageBox.information(self, "저장됨", "목표 자세 가이드가 저장되었습니다.")
        self.close()

    def closeEvent(self, e) -> None:
        self._timer.stop()
        if self._source is not None:
            self._source.release()
        # 추정기는 core.warm 공유 인스턴스 — 닫지 않는다
        super().closeEvent(e)


def _h1(t: str) -> QLabel:
    lb = QLabel(t)
    lb.setStyleSheet("font-size:28px; font-weight:800; margin-bottom:8px;")
    return lb


def _h2(t: str) -> QLabel:
    lb = QLabel(t)
    lb.setStyleSheet("font-size:19px; font-weight:700; color:#4aa8ff; margin-top:12px;")
    return lb


def _wrap(layout) -> QWidget:
    w = QWidget()
    w.setLayout(layout)
    return w
