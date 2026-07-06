# OnLab — 키오스크 AI 체험 게임 앱

카메라로 사람의 자세를 추정(스켈레톤)해 여러 게임을 제공하는 키오스크 앱.
군중 속에서 **주 대상 1명**을 고정 추적한다.

**게임** (홈 화면에서 선택, `ui/game_registry.py` 기반):
- 🧘 **스트레칭 코스** — 안내 자세를 따라 하면 정확도·유지시간 채점 + 유연성 리포트(좌우 비대칭)
- ⚔️ **2인 대결** — 화면을 반씩 나눠 같은 자세로 대결
- ⚡ **반응속도 테스트** — 신호가 뜨면 최대한 빨리 손 들기 (부정 출발 감지)
- 🦘 **높이뛰기** — 제자리 점프 높이를 cm 근사 측정, 목표선 렌더
- 💪 **팔굽혀펴기** — 팔꿈치 각도로 개수 자동 카운트 + 자세(허리 처짐) 피드백

공통 기능: 이름 입력, **게임별 리더보드**, **효과음/음성 안내**, **목표 자세
가이드**(관리자 캡처), **관리자 화면**, **난이도/테마 코스**, 어트랙트 모드.
**데스크톱 앱(PySide6)** 과 **웹앱(`web/`, 브라우저 WASM — 스트레칭/대결만)** 두 가지.
남은 것: 실제 카메라 연결 확인, 임계값 튜닝. (웹앱은 `web/README.md`,
문서 전체는 `docs/overview.md` 참고)

### 데스크톱 앱 주요 파일 (기능 추가분)
- `core/appconfig.py` 앱 UX 설정(자세세트/합격선/타이밍/사운드/미니게임) — `config/app_config.json`
- `core/leaderboard.py` 게임별 리더보드 — `data/leaderboard.json`
- `core/games/` 미니게임 상태머신(반응속도·높이뛰기·팔굽혀펴기, Qt 무관)
- `core/refs.py` 목표 자세 참조 스켈레톤 — `config/refs.json`
- `core/sound.py` 효과음(QtMultimedia) + 음성(espeak-ng 있으면)
- `ui/game_registry.py` · `ui/game_view.py` 게임 목록/공통 뷰 (새 게임 추가 지점)
- `ui/home.py` · `ui/session_view.py` · `ui/admin_dialog.py` 홈/세션/관리자 화면

> 음성 안내는 `espeak-ng` 설치 시 동작: `sudo apt install espeak-ng`
> 헤드리스 UI 검증: `QT_QPA_PLATFORM=offscreen python tools/verify_ui.py` → `out/ui_py/`

## 설치

```bash
pip install -r requirements.txt
# 포즈 모델 번들(최초 1회):
#   models/pose_landmarker_full.task
#   https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
```

## 헤드리스 검증 (창 없이 파일로 확인)

```bash
# 이미지/폴더/영상에 스켈레톤·각도·점수를 그려 out/ 에 저장
python tools/demo_overlay.py testdata/seated_fold.jpg --pose forward_bend --out out/
python tools/demo_overlay.py testdata/                 --out out/           # 폴더 전체
python tools/demo_overlay.py some_video.mp4            --pose tpose --out out/  # 영상 -> overlay.mp4
```

`--pose <name>` 은 `config/poses/<name>.json` 을 채점한다. `--no-track` 으로
주 대상 추적을 끌 수 있다.

## 앱 실행 (B단계 UI)

```bash
python main.py                                   # 카메라 0번, 전체화면
python main.py --source testdata/ --windowed --loop   # 이미지 폴더로 창모드 테스트
python main.py --poses forward_bend tpose --source video.mp4
```

키: `Esc/Q` 종료, `F` 전체화면 토글.

### 디스플레이 없이(ssh/서버) UI 검증

```bash
# 1) offscreen 렌더 후 스크린샷 저장 (제일 간단)
QT_QPA_PLATFORM=offscreen python main.py --source testdata/seated_fold.jpg \
    --loop --windowed --screenshot out/ui/app_shot.png --shot-at 45

# 2) 로컬 화면에 실제 창 띄우기:  ssh -X 로 접속 후 python main.py --windowed
# 3) 가상 디스플레이:  xvfb-run -s "-screen 0 1280x720x24" python main.py --windowed
```

흐름: 대기 → (대상 등장) 카운트다운 → 채점(정확도 게이지 + 유지 바) →
유지 완료 시 점수 → 다음 자세 → 전체 완료 요약.

## 구조

```
core/
  frame_source.py       입력 추상화: ImageSource / VideoFileSource / CameraSource
  pose_estimator.py     PoseEstimator 인터페이스 + PersonPose + 키포인트 표준(33)
  mediapipe_estimator.py  MediaPipe Tasks API(PoseLandmarker) 구현
  tracker.py            주 대상 1명 선택·추적 (bbox 크기 + IoU 유지)
  geometry.py           관절 각도·기울기 유틸
  pose_def.py           자세 정의(JSON) 모델 + 로더
  scorer.py             각도 기반 정확도·점수
tools/demo_overlay.py   헤드리스 검증 도구
config/poses/*.json     자세 정의 5종
models/                 포즈 모델 번들(.task)
testdata/               개발용 샘플 이미지
```

## 자세 정의

각 자세는 지표(metric) 목록으로 정의한다. `angle`(관절 각도)·`lean`(몸통 기울기)를
목표값·허용오차·가중치로 채점한다. `side:"both"` + `aggregate:min/max` 로 좌우
비대칭 자세(한발 서기 등)도 표현한다. 각도 기반이라 신체 크기·화면 위치에 불변이며,
신뢰도 낮은 관절은 자동 제외해 겹침 환경에 대응한다.

기본 5종: `forward_bend`, `side_bend`, `overhead_reach`, `tpose`, `one_leg_balance`.

## 알려진 한계 / 다음 단계

- 정면 단일 카메라는 **깊이(depth) 방향 동작**(비틀기, 다리를 옆으로 든 균형 자세
  일부)의 각도 측정이 부정확할 수 있다. → 3D world 좌표 보조 또는 자세 선정으로 완화.
- 자세별 목표값·허용오차는 **실제 사용자 사진으로 튜닝** 필요(현재는 합리적 초기값).
- B단계: PySide6 전체화면 UI + 세션 상태머신 + 관리자 캡처 화면.
- 카메라 도착 시 `CameraSource` 로 교체만 하면 됨.
