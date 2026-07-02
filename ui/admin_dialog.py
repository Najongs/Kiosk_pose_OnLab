"""관리자 화면: 설정 편집 + 자세 세트 + 목표 자세 참조 캡처 + 초기화."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from core.appconfig import load_app_config, reset_app_config, save_app_config
from core.courses import load_courses, new_course_id, save_courses
from core.leaderboard import clear as clear_leaderboard
from core.pose_def import list_poses, load_pose
from core.refs import (
    clear_ref, has_ref, normalize_pose, pose_to_ref3d, set_ref, set_ref3d,
)


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

        self.guide_sel = QComboBox()
        self.guide_sel.addItem("예시 사진", "image")
        self.guide_sel.addItem("움직이는 캐릭터 (참조 캡처/임포트 필요)", "character")
        if cfg.get("guideStyle") == "character":
            self.guide_sel.setCurrentIndex(1)

        form.addRow("합격 정확도(%)", self.pass_spin)
        form.addRow("카운트다운(초)", self.count_spin)
        form.addRow("결과 표시(초)", self.result_spin)
        hrow = QHBoxLayout()
        hrow.addWidget(self.hold_chk)
        hrow.addWidget(self.hold_spin)
        form.addRow(_wrap(hrow))
        form.addRow("가이드 표시", self.guide_sel)
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

        root.addWidget(_h2("코스 관리"))
        self.course_list = QListWidget()
        self.course_list.setFixedHeight(170)
        self.course_list.itemDoubleClicked.connect(lambda _: self._edit_course())
        root.addWidget(self.course_list)
        crow = QHBoxLayout()
        c_new = QPushButton("+ 새 코스")
        c_new.clicked.connect(self._new_course)
        c_edit = QPushButton("편집")
        c_edit.clicked.connect(self._edit_course)
        c_del = QPushButton("삭제")
        c_del.setObjectName("danger")
        c_del.clicked.connect(self._del_course)
        crow.addWidget(c_new)
        crow.addWidget(c_edit)
        crow.addWidget(c_del)
        crow.addStretch()
        root.addWidget(_wrap(crow))
        self._reload_courses()

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
            "guideStyle": self.guide_sel.currentData(),
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

    # ---- 코스 관리 ----
    _DIFF_COLOR = {"초급": "#2ee6a6", "중급": "#ffdc40", "고급": "#ff5a6a"}

    def _reload_courses(self) -> None:
        from PySide6.QtGui import QColor, QIcon, QPixmap
        from PySide6.QtWidgets import QListWidgetItem
        self.course_list.clear()
        for c in load_courses():
            shuffle = "  ·  🔀 무작위" if c.get("shuffle") else ""
            it = QListWidgetItem(
                f"{c['name']}  ·  {c.get('difficulty','')}  ·  "
                f"{len(c['poses'])}개 자세{shuffle}")
            it.setForeground(QColor("#eef2fb"))  # 팔레트와 무관하게 항상 밝게
            pix = QPixmap(14, 14)
            pix.fill(QColor(self._DIFF_COLOR.get(c.get("difficulty", ""), "#9aa4bd")))
            it.setIcon(QIcon(pix))
            self.course_list.addItem(it)

    def _new_course(self) -> None:
        courses = load_courses()
        dlg = CourseDialog(self._defs, None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            c = dlg.result_course()
            c["id"] = new_course_id(courses)
            courses.append(c)
            save_courses(courses)
            self._reload_courses()

    def _edit_course(self) -> None:
        i = self.course_list.currentRow()
        courses = load_courses()
        if not (0 <= i < len(courses)):
            return
        dlg = CourseDialog(self._defs, courses[i], self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            c = dlg.result_course()
            c["id"] = courses[i].get("id", new_course_id(courses))
            courses[i] = c
            save_courses(courses)
            self._reload_courses()

    def _del_course(self) -> None:
        i = self.course_list.currentRow()
        courses = load_courses()
        if not (0 <= i < len(courses)):
            return
        if QMessageBox.question(
                self, "확인", f"'{courses[i]['name']}' 코스를 삭제할까요?") \
                == QMessageBox.StandardButton.Yes:
            del courses[i]
            save_courses(courses)
            self._reload_courses()


class CourseDialog(QDialog):
    """코스 만들기/편집: 이름·난이도·설명 + 자세 구성(순서 포함)."""

    def __init__(self, defs, course: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("코스 편집" if course else "새 코스")
        self.resize(640, 620)
        self._names = {d.name: d.display_name for d in defs}

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(course["name"] if course else "")
        self.name_edit.setPlaceholderText("예: 아침 스트레칭")
        self.diff_sel = QComboBox()
        self.diff_sel.addItems(["초급", "중급", "고급"])
        if course and course.get("difficulty") in ("초급", "중급", "고급"):
            self.diff_sel.setCurrentText(course["difficulty"])
        self.desc_edit = QLineEdit(course.get("desc", "") if course else "")
        self.desc_edit.setPlaceholderText("코스 설명 (선택)")
        self.shuffle_chk = QCheckBox("🔀 무작위 순서로 재생 (시작할 때마다 섞임)")
        self.shuffle_chk.setChecked(bool(course.get("shuffle")) if course else False)
        form.addRow("이름", self.name_edit)
        form.addRow("난이도", self.diff_sel)
        form.addRow("설명", self.desc_edit)
        form.addRow(self.shuffle_chk)
        root.addLayout(form)

        root.addWidget(_h2("자세 구성"))
        lists = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("전체 자세"))
        self.avail = QListWidget()
        for d in defs:
            self.avail.addItem(d.display_name)
            self.avail.item(self.avail.count() - 1).setData(
                Qt.ItemDataRole.UserRole, d.name)
        self.avail.itemDoubleClicked.connect(lambda _: self._add())
        left_col.addWidget(self.avail)
        lists.addLayout(left_col, 1)

        btns = QVBoxLayout()
        btns.addStretch()
        for label, fn in (("추가 →", self._add), ("← 제거", self._remove),
                          ("▲ 위로", self._up), ("▼ 아래로", self._down)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch()
        lists.addLayout(btns)

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("이 코스의 자세"))
        self.sel = QListWidget()
        for slug in (course["poses"] if course else []):
            if slug in self._names:
                self.sel.addItem(self._names[slug])
                self.sel.item(self.sel.count() - 1).setData(
                    Qt.ItemDataRole.UserRole, slug)
        self.sel.itemDoubleClicked.connect(lambda _: self._remove())
        right_col.addWidget(self.sel)
        lists.addLayout(right_col, 1)
        root.addLayout(lists, 1)

        foot = QHBoxLayout()
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        save = QPushButton("저장")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        foot.addStretch()
        foot.addWidget(cancel)
        foot.addWidget(save)
        root.addLayout(foot)

    def _add(self) -> None:
        it = self.avail.currentItem()
        if it is None:
            return
        slug = it.data(Qt.ItemDataRole.UserRole)
        self.sel.addItem(it.text())
        self.sel.item(self.sel.count() - 1).setData(Qt.ItemDataRole.UserRole, slug)

    def _remove(self) -> None:
        row = self.sel.currentRow()
        if row >= 0:
            self.sel.takeItem(row)

    def _move(self, d: int) -> None:
        row = self.sel.currentRow()
        to = row + d
        if row < 0 or not (0 <= to < self.sel.count()):
            return
        it = self.sel.takeItem(row)
        self.sel.insertItem(to, it)
        self.sel.setCurrentRow(to)

    def _up(self) -> None:
        self._move(-1)

    def _down(self) -> None:
        self._move(1)

    def _save(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "확인", "코스 이름을 입력해 주세요.")
            return
        if self.sel.count() == 0:
            QMessageBox.warning(self, "확인", "자세를 하나 이상 추가해 주세요.")
            return
        self.accept()

    def result_course(self) -> dict:
        poses = [self.sel.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.sel.count())]
        return {
            "name": self.name_edit.text().strip(),
            "difficulty": self.diff_sel.currentText(),
            "desc": self.desc_edit.text().strip(),
            "poses": poses,
            "shuffle": self.shuffle_chk.isChecked(),
        }


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
        r3 = pose_to_ref3d(self._last_primary)
        if r3:
            set_ref3d(self._pose, r3)  # 회전 캐릭터용 3D 참조
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
