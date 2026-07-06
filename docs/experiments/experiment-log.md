# 실험·시도 기록

> 개발 과정에서 시도했다가 바꾸거나 폐기한 것들의 기록. **같은 실험을 반복하지 않기 위한 문서.**
> 커밋 해시는 `git show <해시>`로 상세 확인 가능.

## 1. 3D 캐릭터 가이드 — 실시간 렌더링 → 베이크 스프라이트로 전환

목표: "따라해 보세요" 박스에 리깅된 3D 캐릭터가 목표 자세를 시연.

| 시도 | 결과 | 커밋 |
|---|---|---|
| 캐릭터 에셋 드롭 폴더 + 포맷 가이드(리깅 GLB) | 채택 | `a433578` |
| FBX 직접 수용 (서버측 FBX2glTF 변환) | 채택 — Mixamo FBX 바로 사용 가능 | `fb12a0d` |
| Mixamo 리깅 Cinto 캐릭터(46본) + 웹 three.js 스캐폴드 | 채택 | `044ed81` |
| **QtQuick3D 실시간 렌더링** (QQuickWidget, guideStyle=mesh3d) | ❌ QQuickWidget이 아무것도 그리지 않음 | `a34c2b0`, `554ef73` |
| QQuickView 윈도 컨테이너로 교체 | ⚠️ 그려지긴 하나 일부 GPU 드라이버에서 크래시 | `b5c1959` |
| **베이크 스프라이트** (`tools/bake_character.py` 소프트웨어 래스터라이저로 glb → PNG 시퀀스) | ✅ **최종 채택** — GPU 무관, 크래시 없음 | `784400f` |
| 포즈 리타게팅 — `refs3d.json` 기준자세를 캐릭터 본에 적용해 자세별 시연 스프라이트 베이크 | ✅ 채택 | `1996281` |

**교훈**: 키오스크(사양 미상 GPU)에서 실시간 3D는 위험. 오프라인 베이크가 안정적.
실시간 경로는 `ONLAB_QTQUICK3D=1` 환경변수 뒤에 보존되어 있음 (`ui/char3d_widget.py`).
웹 쪽 three.js 캐릭터(`web/src/character3d.ts`)는 본 리타게팅이 "2단계(예정)" — 현재 내장 애니메이션+턴테이블만.

## 2. 카메라 협상 — Windows 카메라 열기 안정화

증상: Windows에서 카메라가 안 열리거나, 열려도 저FPS/프레임 미전달.

| 시도 | 결과 | 커밋 |
|---|---|---|
| MSMF 우선 + MJPG 강제, 640×480 폴백 | ⚠️ 일부 장치에서 행(hang) | `5dfe3de` |
| "실제로 프레임이 나오는 조합"만 채택하도록 검증 추가 | 개선 | `ac0e02b` |
| **DSHOW 전용 사다리, MSMF는 타임아웃 가드 걸고 최후순위로 강등** | ✅ 채택 | `d2b981a` |
| min_fps(기본 15) 이상 나오는 최고 해상도 자동 선택 | ✅ 채택 | `cc576f5` |
| 스캔 결과 디스크 캐시, 재스캔은 관리자 메뉴에서만 | ✅ 채택 (부팅 시간 단축) | `42a94fc` |

**교훈**: Windows 카메라 백엔드는 DSHOW가 안전 기본값. "열림"과 "프레임 전달"은 별개로 검증해야 함.

## 3. 성능 — 표시 FPS와 추론 FPS 분리

증상: 추론(~10fps)이 UI 스레드를 막아 화면 전체가 버벅임.

| 시도 | 결과 | 커밋 |
|---|---|---|
| 카메라/모델을 UI 스레드에서 분리 + 모델 웜 캐시 | 개선 | `5dd6b4b` |
| 2단계 파이프라인 워커 (표시 FPS ≠ 추론 FPS) | 개선 | `7452a92` |
| **MediaPipe LIVE_STREAM 비동기 모드** (`detect_async` — GIL 해제) | ✅ 채택 — 표시가 카메라 FPS 유지 | `8a65a93` |

**교훈**: Python에서는 스레드 분리만으론 부족 (GIL). MediaPipe LIVE_STREAM이 네이티브에서 GIL을 풀어줘야 진짜 병렬.

## 4. Windows 한글 이슈

| 문제 | 해결 | 커밋 |
|---|---|---|
| `cv2.imread`가 한글 경로에서 None 반환 | `np.fromfile`+`imdecode` 우회 | `ee1fc62` |
| cv2로 한글 텍스트 렌더 불가 + Windows 폰트 상이 | Pillow 렌더링, 폰트 자동 탐색 + `ONLAB_FONT` 재정의 | `b348524` |

## 5. 음성/사운드

- **espeak-ng TTS**: 한국어 발음 품질이 낮아 **voice 기본 off** (`core/appconfig.py`). 필요 시 관리자에서 켤 수 있음. 고품질 TTS(클라우드)는 오프라인 요건과 충돌해 보류.
- BGM은 `assets/bgm/`에 파일만 넣으면 루프 재생 — 저작권 문제로 음원은 리포에 미포함.

## 6. 배포 — PyInstaller onefile vs onedir

- **onefile 폐기**: 앱이 실행 중 `config/`(설정·리더보드·카메라 캐시)에 기록하는데, onefile은 임시폴더에 풀려 기록이 소실됨.
- **onedir 채택** (`tools/build_exe.py` → `dist/OnLab/`, 약 700MB): `_internal/config/`에 기록 유지. 상세는 [배포 가이드](../deploy/build-guide.md). (`0885597`)
- Windows exe는 Windows에서만 빌드 가능 (교차 빌드 불가).

## 7. 포즈 탐지 안정화 — 모델 선택 + One Euro 스무딩 (2026-07)

증상: 키포인트가 프레임마다 떨려 채점·게이지가 흔들림.

원인 3가지를 발견해 모두 수정:

| 문제 | 수정 | 근거 |
|---|---|---|
| `_default_model()`이 **lite 모델을 우선** 선택 (3종 중 가장 불안정) | 기본 full, `settings.json pose_estimator.model`("lite"/"full"/"heavy")로 선택 | 아래 벤치마크 |
| 우리 쪽 **시간적 스무딩 없음** | One Euro Filter(`core/smoothing.py`) — 트래커(주 대상)와 대결(자리별)에 적용, `tracker.smoothing` 로 on/off | 합성 3px 떨림 2.9→1.1px, 20px/frame 이동 시 지연 7px |
| LIVE_STREAM 타임스탬프가 고정 +33ms (실제 fps 무관) | `time.monotonic()` 기반 실제 시각 — MediaPipe 내부 랜드마크 필터가 시간 간격 기반 | 코드 확인 |

**벤치마크** (`tools/bench_pose.py`, 같은 이미지+노이즈 40프레임, 이 NAS CPU):

| 모델 | 떨림(raw) | 떨림(필터 후) | 추론 ms |
|---|---|---|---|
| lite | 0.77px | 0.63px | 42 |
| **full (신규 기본)** | 0.44px | 0.51px | 48 |
| heavy | 0.32px | 0.30px | 118 |

**교훈**: full 이 최적점 — lite 대비 15% 느린데 떨림 43% 감소. heavy 는 2.8배
느려 반응속도 게임 지연에 영향 → 고사양 키오스크에서만 옵션으로.
heavy 모델(30MB)은 리포 미포함 — .gitignore 의 다운로드 URL 참고.
스무딩 필터는 **동일인 추적이 보장되는 지점**(트래커 뒤)에 걸어야 하며, 사람이
바뀌면 reset 필수(이전 궤적에 이어붙으면 순간이동 잔상). 단위 테스트
`tools/test_smoothing.py`.

## 8. 미해결 / 알려진 한계

- 단일 정면 카메라 → 깊이 방향 동작(비틀기, 일부 균형 자세) 측정 부정확. 자세 설계 시 정면 평면 동작 위주로.
- 자세 목표각/허용치는 "합리적 초기값" — 실사용자 사진 기반 튜닝 필요.
- `core/tracker.py`의 `center_weight` 설정값이 실제 로직에 미적용 (면적 기반만 동작). 웹의 `pickPrimary`는 더 단순(최대 bbox만, IoU 추적 없음).
- `tools/import_poses.py`에 dry-run 분기 `[예정]` 상태.
