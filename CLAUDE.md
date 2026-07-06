# CLAUDE.md

OnLab — MediaPipe 자세추정 기반 키오스크 **AI 체험 게임** 앱.
카메라로 33키포인트 골격을 추정해 여러 미니게임을 제공: 스트레칭 코스(정확도·유지 채점), 2인 대결, 반응속도 테스트, 높이뛰기, 팔굽혀펴기. 게임별 리더보드, 유연성 리포트(좌우 비대칭), 관리자 화면, 어트랙트 모드 포함.

## 게임 구조 (레지스트리)

홈 화면 카드·네비게이션·리더보드 탭은 전부 `ui/game_registry.py`의 `REGISTRY`에서 나온다. **새 게임 추가 절차**:
1. `core/games/<게임>.py` — Qt 무관 상태머신 (`update(primary, now) -> State`, 시간·난수 주입 — `core/session.py` 패턴)
2. `ui/game_renderers.py` — `compose_<게임>(disp, primary, state, anim_t)` (HUD 프리미티브는 `ui/hud.py` 재사용)
3. `ui/<게임>_view.py` — `MiniGameView`(`ui/game_view.py`) 서브클래스: `game_id`, `_make_game(cfg)`, `_compose` 만 정의
4. `REGISTRY`에 `GameDef` 한 줄 추가 → 홈 카드/전환/리더보드 탭 자동 생성
5. `tools/test_games.py`(합성 골격 상태 전이) + `tools/verify_games.py`(오프스크린 렌더)에 케이스 추가

워커 수명주기(카메라·추론 스레드)는 `BaseGameView`가 담당 — SessionView/VersusView 도 이 위에 있다. 두 뷰의 `begin` 시그니처는 변경 금지 (`tools/verify_ui.py` 등이 positional 호출).

## 이중 구현 (가장 중요한 구조적 사실)

- **데스크톱** (루트): Python 3.12 + PySide6, MediaPipe `.task` 네이티브 추론. 물리 키오스크용.
- **웹** (`web/`): Vite + TypeScript, `@mediapipe/tasks-vision` WASM(브라우저 내 추론) + three.js. `web/src/`는 `core/`를 파일 단위로 미러링 (`scorer.ts` = `scorer.py` 포팅 등).

**⚠️ 채점 로직(`core/scorer.py` ↔ `web/src/scorer.ts`)을 수정하면 반드시 양쪽을 함께 수정**하고 `cd web && npm test`로 parity 테스트(오차 <0.01) 통과를 확인할 것. 자세 정의 JSON 스키마도 양쪽 공유.

## 아키텍처

```
main.py → ui/main_window.py (홈 + 게임 뷰 지연 생성, game_registry 기반)
core/  Qt 비의존 파이프라인: frame_source → mediapipe_estimator(LIVE_STREAM 비동기)
       → tracker(주 피사체 1명) → session 상태머신(IDLE→COUNTDOWN→SCORING→RESULT→DONE)
         └ scorer(관절각 기반, 체격·위치 무관) + hold(유지 판정) + report(비대칭)
core/games/  미니게임 상태머신: reaction(반응속도)·jump(높이뛰기)·pushup(팔굽혀펴기)
ui/    game_view(BaseGameView/MiniGameView — 워커 스레드 수명주기 공통),
       session_view/versus_view/reaction_view/jump_view/pushup_view,
       renderer+game_renderers(HUD 합성), hud(공용 프리미티브),
       home(게임 카드 + 코스 서브페이지 + 게임별 리더보드 탭),
       admin_dialog(PIN 기본 4000, 코스 편집·기준자세 캡처),
       attract(유휴 시 라이브 미러 호객 — 실시간 스켈레톤 + 랜덤 플러시, 슬라이드쇼 폴백)
tools/ build_exe(PyInstaller), verify_ui/verify_versus/verify_games(헤드리스 스크린샷),
       test_games(합성 골격 상태머신 테스트),
       import_poses(이미지→자세 JSON 자동 생성), bake_character(glb→스프라이트 베이크)
```

상세: `docs/dev/architecture.md`

## 실행·검증 명령

```bash
python main.py --source testdata/tree_balance.jpg --windowed  # 카메라 없이 실행
python main.py --source testdata/ --loop                      # 폴더 순환
python tools/verify_ui.py        # 오프스크린 UI 스크린샷 → out/ui_py/ (Python 테스트 대용)
python tools/test_games.py       # 미니게임 상태머신 테스트 (합성 골격 + 가짜 시간)
python tools/verify_games.py     # 미니게임 뷰 오프스크린 렌더 + 리더보드 기록 확인
python tools/demo_overlay.py <이미지/폴더/영상> [--pose <이름>]  # 헤드리스 채점 오버레이 → out/
cd web && npm test               # Vitest: 채점 parity + versus
python tools/build_exe.py        # Windows 전용 PyInstaller onedir 빌드
```

Python 단위테스트 디렉토리는 없음 — 검증은 위 헤드리스 스크립트로. 웹은 Vitest.

## 지켜야 할 규칙 (실험으로 확정된 것 — `docs/experiments/experiment-log.md` 참고)

1. **numpy<2.0 고정** (MediaPipe 호환, `requirements.txt`)
2. **QtQuick3D 실시간 캐릭터 금지(기본)** — 일부 GPU 드라이버 크래시 이력. 캐릭터 가이드는 `tools/bake_character.py` 베이크 스프라이트가 기본. 실시간 경로는 `ONLAB_QTQUICK3D=1` 뒤에만 존재
3. **코스 저장은 `core/courses.py` 경유** — `web/public/courses.json` 미러 동기화가 여기서 일어남
4. **cv2로 한글 텍스트/경로 다루지 말 것** — 텍스트는 Pillow 렌더링, 이미지 읽기는 한글 경로 우회 로직 사용 (Windows에서 깨짐)
5. **Windows 카메라는 DSHOW 사다리 유지** — MSMF는 행(hang) 이력으로 최후순위. 카메라 스캔 결과는 디스크 캐시됨(재스캔은 관리자 메뉴)
6. **배포는 onedir만** — 앱이 런타임에 `config/`에 기록하므로 onefile 불가
7. 추론은 반드시 워커 스레드 + MediaPipe LIVE_STREAM 비동기 유지 (UI 스레드에서 추론 시 화면 버벅임)
8. **키포인트 스무딩은 동일인 추적이 보장되는 지점(트래커 뒤/대결 자리별)에만** — 사람이 바뀌면 reset 필수. 모델은 full 기본(lite 는 떨림 심함, heavy 는 2.8배 느림 — `tools/bench_pose.py`로 재측정)
9. **사용자 표시 문구는 한국어(주) + 영어(작은 보조) 병기** — 새 문구를 추가하면 `core/i18n.py`의 `EN` 사전(동적 문구는 `_PATTERNS`)에 짝을 등록할 것. HUD 는 `msg_pill`/`splash_text`가 자동 병기, Qt 라벨은 rich text 로 직접

## 설정 파일

| 파일 | 내용 |
|---|---|
| `config/settings.json` | 엔진: 카메라·추정기(model: lite/full/heavy, 기본 full)·추적기(smoothing: One Euro 필터)·채점(pass 85%, hold 3s) |
| `config/app_config.json` | UX: 코스, 타이밍, 사운드, 관리자 PIN, guideStyle (기본값은 `core/appconfig.py`) |
| `config/poses/*.json` | 자세 정의 (angle/lean 메트릭, `side:"both"`+`aggregate` 지원) |
| `config/courses.json` | 코스 (웹에 자동 미러) |
| `config/refs.json`/`refs3d.json` | 관리자 캡처 기준자세 (2D/3D) |
| `models/pose_landmarker_{full,lite}.task` | MediaPipe 모델 (별도 다운로드) |

## 문서

`docs/overview.md`가 문서 지도 (한·영 병기). dev/(아키텍처·SRS), content/(아이디어 분석), deploy/(빌드 가이드), experiments/(시도·전환 기록 — **폐기한 접근을 다시 시도하기 전에 반드시 확인**), meetings/. 문서 파일·폴더명은 영어 kebab-case.

## 알려진 한계

- 단일 정면 카메라 → 깊이 방향 동작(비틀기 등) 측정 부정확
- 자세 목표각/허용치는 초기값 — 실사용자 데이터로 튜닝 필요
- TTS(espeak-ng)는 한국어 품질 문제로 기본 off, BGM 음원은 리포 미포함(`assets/bgm/`에 직접 추가)
