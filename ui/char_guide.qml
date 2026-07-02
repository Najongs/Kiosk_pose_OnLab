// 리깅 캐릭터 가이드 — RuntimeLoader 로 glb 를 로드해 턴테이블로 보여준다.
// characterUrl 컨텍스트 프로퍼티는 파이썬(CharacterWidget)에서 주입.
import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils

Rectangle {
    id: rootItem
    color: "#c010141f"
    radius: 14
    border.color: "#8896b4dc"
    border.width: 2

    View3D {
        id: view
        anchors.fill: parent
        anchors.margins: 4
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
        }
        PerspectiveCamera {
            id: cam
            fieldOfView: 35
            position: Qt.vector3d(0, 95, 300)
        }
        DirectionalLight { eulerRotation.x: -25; brightness: 1.5 }
        DirectionalLight { eulerRotation.y: 140; brightness: 0.7 }

        Node {
            id: holder
            SequentialAnimation on eulerRotation.y {
                loops: Animation.Infinite
                NumberAnimation { from: -35; to: 35; duration: 2800
                                  easing.type: Easing.InOutSine }
                NumberAnimation { from: 35; to: -35; duration: 2800
                                  easing.type: Easing.InOutSine }
            }
            RuntimeLoader {
                id: loader
                source: characterUrl
                onStatusChanged: {
                    if (status === RuntimeLoader.Success) {
                        // 모델 크기에 맞춰 카메라 자동 프레이밍
                        var b = loader.bounds
                        var cy = (b.maximum.y + b.minimum.y) / 2
                        var h = Math.max(1, b.maximum.y - b.minimum.y)
                        cam.position = Qt.vector3d(0, cy + h * 0.05, h * 1.55)
                        cam.lookAtNode = loader
                    }
                }
            }
        }
    }

    Text {
        anchors.top: parent.top
        anchors.topMargin: 8
        anchors.horizontalCenter: parent.horizontalCenter
        text: "따라해 보세요"
        color: "#c8dcff"
        font.pixelSize: Math.max(13, rootItem.height / 22)
        font.bold: true
    }
}
