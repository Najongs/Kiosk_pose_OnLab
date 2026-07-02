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
    """CharacterWidget 생성 시도 — 실패하면 None (호출측 폴백).

    QQuickWidget 은 일부 Windows 환경에서 반투명 합성이 조용히 실패해
    아무것도 그리지 않는다. QQuickView + createWindowContainer(네이티브
    자식 윈도우)는 D3D 스왑체인을 직접 가져 훨씬 안정적이다."""
    glb = find_character_glb()
    if glb is None:
        print(f"[3D 가이드] glb 없음: {_CHAR_DIR}")
        return None
    if not os.path.isfile(_QML):
        print(f"[3D 가이드] QML 없음: {_QML}")
        return None
    try:
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QColor
        from PySide6.QtQuick import QQuickView
        from PySide6.QtWidgets import QWidget

        view = QQuickView()
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        view.setColor(QColor("#10141f"))
        view.sceneGraphError.connect(
            lambda err, msg: print("[3D 가이드] 씬그래프 오류:", msg))
        view.rootContext().setContextProperty(
            "characterUrl", QUrl.fromLocalFile(glb).toString())
        view.setSource(QUrl.fromLocalFile(_QML))
        print(f"[3D 가이드] glb: {os.path.basename(glb)}, QML 상태: {view.status()}")
        if view.status() == QQuickView.Status.Error or view.rootObject() is None:
            for e in view.errors():
                print("[3D 가이드] QML 오류:", e.toString())
            view.deleteLater()
            return None
        container = QWidget.createWindowContainer(view, parent)
        container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        container.hide()
        return container
    except Exception as e:
        print("[3D 가이드] 초기화 실패 — 기본 캐릭터 사용:", e)
        return None
