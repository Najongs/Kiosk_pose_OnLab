# 아키텍처 개요

## 한눈에 보기

OnLab은 **두 개의 병렬 구현**을 가진다. 자세 정의 JSON 스키마와 채점 알고리즘을 공유한다.

| | 데스크톱 (루트) | 웹 (`web/`) |
|---|---|---|
| 언어/프레임워크 | Python 3.12 + PySide6 | TypeScript + Vite |
| 추론 | MediaPipe Tasks `.task` (네이티브) | `@mediapipe/tasks-vision` (WASM, 브라우저 내) |
| 용도 | 오프라인 물리 키오스크 | 사용자 기기 배포 (영상이 기기를 떠나지 않음) |
| 저장 | `config/`, `data/` 파일 | `localStorage` (`onlab.*`) |
| 배포 | PyInstaller onedir | 정적 파일 호스팅 |

두 구현의 채점 일치는 `web/test/parity.test.ts`가 검증한다 (오차 <0.01).

## 파이프라인

```
FrameSource(카메라/이미지/영상)
  → MediaPipeEstimator (33키포인트 + 3D world landmarks, 다인)
  → PrimarySubjectTracker (군중 속 1명 고정: IoU + grace_frames)
  → Session 상태머신 (IDLE → COUNTDOWN → SCORING → RESULT → … → DONE)
      ├ PoseScorer   관절각/기울기 vs 목표±허용치 → 가중평균 정확도
      ├ HoldEvaluator 임계값 n초 유지 판정 (drop_grace 흔들림 유예)
      └ report.analyze  관절별 ROM 등급 + 좌우 비대칭(≥12° 경고)
  → renderer.compose  스켈레톤 + HUD(게이지·유지바·콤보·등급·컨페티) + 가이드
```

## 게임 레지스트리 (2026-07 추가)

앱은 이제 다중 게임 구조다. 홈 화면 카드·화면 전환·리더보드 탭은 전부
`ui/game_registry.py`의 `REGISTRY`(GameDef 목록)에서 파생되고, `MainWindow`는
선택된 게임의 뷰를 지연 생성해 QStackedWidget 에 추가한다.

| 게임 | 로직 | 뷰 | 렌더러 |
|---|---|---|---|
| 스트레칭 코스 (stretch) | `core/session.py` + Engine | `ui/session_view.py` | `ui/renderer.py compose()` |
| 2인 대결 (versus) | `core/versus.py` | `ui/versus_view.py` | `compose_versus()` |
| 반응속도 (reaction) | `core/games/reaction.py` | `ui/reaction_view.py` | `ui/game_renderers.py` |
| 높이뛰기 (jump) | `core/games/jump.py` | `ui/jump_view.py` | 〃 |
| 팔굽혀펴기 (pushup) | `core/games/pushup.py` | `ui/pushup_view.py` | 〃 |

- **`ui/game_view.py`**: `BaseGameView`(워커 스레드 수명주기·표시·실패 처리 공통)와
  `MiniGameView`(1인 게임용 — 추정기+추적기+게임 객체 조립, 사운드 큐, 리더보드 기록).
  모든 게임 뷰가 이 위에 있다. 새 미니게임은 `game_id`/`_make_game`/`_compose`만 정의.
- **`ui/hud.py`**: 게임 공용 HUD 프리미티브 (등급 배지, 메시지 필, 진행 도트,
  컨페티, 카운트다운 링) — `renderer.py`에서 추출.
- **미니게임 상태머신**은 `core/session.py` 패턴 미러: State Enum + 렌더 계약
  dataclass + `update(primary, now)`, 시간·난수(rng) 주입으로 헤드리스 테스트 가능
  (`tools/test_games.py`).
- **리더보드**는 기록별 `game` 키로 분리 (`top_n(n, game=...)`), 과거 기록은
  stretch 로 간주. 홈에 게임별 탭.

## 데스크톱 모듈 구조

### `core/` — Qt 비의존 (헤드리스 툴과 공유)
| 파일 | 책임 |
|---|---|
| `pose_estimator.py` | 추정기 인터페이스, `PersonPose`, 33키포인트 표준(이름/엣지) |
| `mediapipe_estimator.py` | LIVE_STREAM 비동기 추론 (GIL 해제 → 표시 FPS 유지), lite/full 모델 |
| `tracker.py` | 주 피사체 선정(면적 기반) + IoU 동일성 유지 |
| `geometry.py` | 관절각·기울기 계산 |
| `pose_def.py` | 자세 정의 JSON 로더 (`_mid` 중점, `side: both` + `aggregate: min/max`) |
| `scorer.py` | `score = max(0, 100*(1-err/(2*tol)))` 가중평균, 저가시성 관절 자동 제외 |
| `hold.py` | 유지 판정, 유지 구간 시간가중 평균이 최종 점수 |
| `session.py` | 1인 세션 상태머신, 콤보(+2/연속, 최대 +10), 시간은 float 주입(테스트 용이) |
| `versus.py` | 2인 대결: 화면 좌/우 배정, 중복검출 제거, 승패 |
| `report.py` | 유연성 리포트 (최상/우수/양호/개선 필요) |
| `refs.py` | 기준자세 스켈레톤 (2D `refs.json` + 3D `refs3d.json`, 관리자 캡처) |
| `courses.py` | 코스 로드/저장 + **`web/public/courses.json` 미러 동기화** |
| `engine.py` | 추정기+추적기+채점기+세션 조립, `load_settings()` |
| `warm.py` | 앱 수명 공유 추정기 캐시 (세션마다 모델 재로드 방지) |
| `frame_source.py` | 카메라/이미지/영상 추상화 + 카메라 모드 캐시 |
| `appconfig.py` | UX 설정 기본값 (`DEFAULT_APP_CONFIG`) |
| `i18n.py` | 한국어 문구의 영어 보조 표기 사전 (`en()`) — 외국인 방문객용 병기, HUD 는 msg_pill/splash 가 자동 적용 |
| `sound.py` / `bgm.py` / `leaderboard.py` / `drawing.py` | 효과음·TTS / BGM / 리더보드 / 그리기 프리미티브 |

### `ui/` — PySide6
| 파일 | 책임 |
|---|---|
| `main_window.py` | QStackedWidget(홈/세션/대결) + 관리자 + 어트랙트 타이머 + BGM |
| `home.py` | 이름 입력, 빠른 시작, 코스 카드, 리더보드 |
| `session_view.py` | 핵심 뷰 — 추론·합성은 워커 스레드, UI 스레드는 QPixmap 표시만. `render_once()`로 헤드리스 검증 |
| `versus_view.py` | 2인 분할 화면 |
| `admin_dialog.py` | PIN 게이트, 설정, 코스 편집기, 기준자세 캡처, 초기화 |
| `renderer.py` | `compose()`/`compose_versus()` + `draw_guide()` (가이드 3종: image/character/mesh3d 스프라이트) |
| `frame_worker.py` | QThread 추론+렌더 루프 |
| `char3d_widget.py`+`char_guide.qml` | 실시간 QtQuick3D 캐릭터 (`ONLAB_QTQUICK3D=1` 필요 — 기본 비활성) |
| `attract.py` | 유휴 시 라이브 미러(실시간 스켈레톤 호객) + 슬라이드쇼 폴백 |
| `hud.py` | 게임 공용 HUD/연출 프리미티브 (스포트라이트·트레일·팝업·스플래시 등) |

### `web/src/` — 데스크톱과 파일 단위 미러
`scorer.ts`(=`scorer.py` 포팅), `session.ts`, `versus.ts`, `hold.ts`, `report.ts`, `guide.ts`, `character3d.ts`(three.js), `main.ts`(컨트롤러). `web/public/`에 모델·WASM·자세 JSON·`character.glb`를 번들해 오프라인/인트라넷 동작.

## 설정·데이터 파일

| 파일 | 내용 |
|---|---|
| `config/settings.json` | 엔진: 카메라(1280×720@30, min_fps 15), 추정기(model: lite/full/heavy — 기본 full), 추적기(smoothing: One Euro 스무딩 on/off), 채점(pass 85, hold 3s) |
| `config/app_config.json` | UX: 코스, 카운트다운/결과 시간, 사운드/BGM, 관리자 PIN(기본 4000), 어트랙트 45s, guideStyle |
| `config/courses.json` | 코스 5종 — 저장 시 `web/public/`에 자동 미러 |
| `config/poses/*.json` | 자세 정의 5종 (forward_bend, side_bend, overhead_reach, tpose, one_leg_balance) |
| `config/refs.json` / `refs3d.json` | 관리자 캡처 기준자세 (2D/3D) |
| `data/leaderboard.json` | 리더보드 (런타임 기록) |

## 검증 방법 (Python 단위테스트 없음 — 헤드리스 스크립트 사용)

```bash
python main.py --source testdata/tree_balance.jpg --windowed   # 카메라 없이 실행
python tools/verify_ui.py        # 오프스크린 UI 스크린샷 → out/ui_py/
python tools/verify_versus.py    # 대결 화면 스크린샷
python tools/test_games.py       # 미니게임 상태머신 테스트 (합성 골격 + 가짜 시간)
python tools/verify_games.py     # 미니게임 뷰 오프스크린 렌더 + 리더보드 확인
python tools/demo_overlay.py <이미지/폴더/영상> [--pose <이름>]  # 스켈레톤·점수 오버레이 → out/
cd web && npm test               # Vitest — 채점 parity + versus
```

## 지켜야 할 규칙

1. **Python↔TS parity**: `core/scorer.py` 수정 시 `web/src/scorer.ts`도 동일하게 수정하고 `web/test/parity.test.ts` 통과 확인
2. **courses 미러**: 코스는 `core/courses.py`를 통해 저장해야 웹 미러가 동기화됨
3. **numpy<2.0** 고정 (MediaPipe 호환)
4. **QtQuick3D 사용 금지(기본)**: 일부 GPU 드라이버 크래시 이력 → 캐릭터 가이드는 베이크 스프라이트가 기본 (`docs/experiments/experiment-log.md` 참고)
5. cv2는 한글을 못 그림 → 텍스트 렌더링은 Pillow 경유 (`ONLAB_FONT`로 폰트 재정의 가능)
