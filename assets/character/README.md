# 가이드 캐릭터 메시

움직이는 가이드 캐릭터용 3D 모델을 이 폴더에 넣어 주세요.

## 권장 형식: `.glb` (binary glTF)
- **리깅(뼈대) 포함 필수** — 뼈가 없으면(obj 등) 움직일 수 없습니다.
- 텍스처가 파일 안에 포함된 단일 `.glb` 파일 (외부 이미지 참조 X)
- 기본 자세: **T-포즈**
- 뼈대: **Mixamo 리그** 또는 **VRM 휴머노이드** 표준 본 이름이면
  관절 리타게팅이 쉬워 가장 좋습니다.
- 폴리곤: 5만 트라이앵글 이하 권장 (키오스크 CPU/내장그래픽 고려)

## 형식별 비교
| 형식 | 리깅 | 판정 |
|------|------|------|
| .glb / .gltf | O | ✅ 권장 (three.js/QtQuick3D 표준) |
| .vrm | O (표준 본) | ✅ 좋음 (glTF 기반, 리타게팅 최적) |
| .fbx | O | ✅ 그대로 올려도 됨 — 서버에서 FBX2glTF 로 변환해 드림 |
| .blend | O | △ Blender 전용 — Blender 에서 File > Export > glTF 2.0(.glb) 로 한 번 내보내서 올려주세요 |
| .ma / .mb (Maya) | O | △ Maya 전용 — Maya 에서 File > Export All > FBX 로 내보내서 올려주세요 |
| .obj | X | ❌ 정적 메시 — 뼈대가 없어 애니메이션 불가 |

## 모델이 없다면
- 사람 사진/모델을 https://www.mixamo.com 에 올리면 자동 리깅됩니다
  (Download: Format=FBX → Blender 에서 .glb 로 export).
- 무료 리깅 캐릭터: Mixamo 기본 캐릭터, Quaternius, Kenney 등.

## 현재 상태
- **`Cinto_legging.fbx` = 공식 캐릭터** (Mixamo 리깅: 본 46개·스킨 웨이트·
  텍스처 내장 확인 완료) → `Cinto_legging.glb` 로 변환됨.
  `web/public/character.glb` 에 배치되어 웹앱 3D 가이드가 이 캐릭터를 사용.
- `Cinto.fbx` 는 리깅 없는 원본 (참고용), `Box Turn.fbx` 는 Mixamo Y-Bot
  테스트 파일.
- 다음 단계: 목표 자세 관절 데이터로 본 리타게팅 → 캐릭터가 자세 시연.

새 캐릭터로 바꾸려면: 리깅된 FBX/GLB 를 이 폴더에 넣고 알려주세요.
glb 변환 후 `web/public/character.glb` 를 교체하면 됩니다.
