"""리깅 캐릭터(glb) 3D 가이드 위젯 — QtQuick3D RuntimeLoader 기반.

세션 화면 위 가이드 박스 자리에 오버레이로 띄운다. QtQuick3D 미지원 환경
(GPU/드라이버 문제 등)이나 glb 부재 시에는 생성이 실패하고, 호출측은
기존 절차적 캐릭터로 폴백한다.
"""

from __future__ import annotations

import glob
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHAR_DIR = os.path.join(_ROOT, "assets", "character")
_QML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "char_guide.qml")


def find_character_glb() -> str | None:
    """assets/character/ 의 첫 .glb (없으면 None)."""
    files = sorted(glob.glob(os.path.join(_CHAR_DIR, "*.glb")))
    return files[0] if files else None


def create_character_widget(parent=None):
    """CharacterWidget 생성 시도 — 실패하면 None (호출측 폴백)."""
    glb = find_character_glb()
    if glb is None or not os.path.isfile(_QML):
        return None
    try:
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtQuickWidgets import QQuickWidget

        w = QQuickWidget(parent)
        w.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        w.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
        w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        w.setClearColor(Qt.GlobalColor.transparent)
        w.rootContext().setContextProperty(
            "characterUrl", QUrl.fromLocalFile(glb).toString())
        w.setSource(QUrl.fromLocalFile(_QML))
        if w.status() == QQuickWidget.Status.Error or w.rootObject() is None:
            for e in w.errors():
                print("[3D 가이드] QML 오류:", e.toString())
            w.deleteLater()
            return None
        w.hide()
        return w
    except Exception as e:
        print("[3D 가이드] 초기화 실패 — 기본 캐릭터 사용:", e)
        return None
