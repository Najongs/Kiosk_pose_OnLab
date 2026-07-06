# OnLab 문서 개요 · Documentation Overview

*(한국어 먼저, English below)*

**OnLab**은 MediaPipe 자세추정 기반 키오스크 **AI 체험 게임** 앱이다. 카메라로 사용자의 골격(33키포인트)을 추정해 여러 게임을 제공한다: 스트레칭 코스(정확도·유지 채점 + 유연성 리포트), 2인 대결, 반응속도 테스트, 높이뛰기, 팔굽혀펴기. 게임별 리더보드와 관리자 화면, 어트랙트 모드를 갖췄다. 데스크톱(Python+PySide6)과 웹(TypeScript+WASM, 스트레칭만) 두 구현이 채점 로직을 공유한다.

## 문서 지도

| 폴더 | 문서 | 내용 | 대상 |
|---|---|---|---|
| [dev/](dev/) | [architecture.md](dev/architecture.md) | 모듈 구조, 파이프라인, 검증 방법, 지켜야 할 규칙 | 개발자 (신규 합류 시 첫 문서) |
| | [game-structure-revamp-2026-07.md](dev/game-structure-revamp-2026-07.md) | 게임 선택 홈 + 미니게임 3종(반응속도·높이뛰기·팔굽혀펴기) 추가 작업 기록 | 개발자 |
| | [srs-template.md](dev/srs-template.md) | SRS 템플릿 — 기능/비기능/AI 요구사항 정의 양식 | 기획·개발 |
| [content/](content/) | [idea-feasibility.md](content/idea-feasibility.md) | 행사용 콘텐츠 아이디어 등급 분류 + 상위 후보 구현 방향 | 기획·개발 |
| | [game-references.md](content/game-references.md) | 참여 유도 설계 근거 조사 (허니팟 효과·어트랙트·피드백, 출처 검증) | 기획·개발 |
| | [engagement-improvements.md](content/engagement-improvements.md) | 연구 근거 기반 개선안 우선순위 + 로드맵 (1순위: 어트랙트 라이브 미러) | 기획·개발·운영 |
| [deploy/](deploy/) | [build-guide.md](deploy/build-guide.md) | GitHub Actions·PyInstaller 빌드, 키오스크 설치·자동실행, 트러블슈팅 | 운영·개발 |
| | [event-checklist.md](deploy/event-checklist.md) | 배치·시연·안내 멘트 등 현장 운영 가이드 (연구 근거 기반) | 운영 |
| [experiments/](experiments/) | [experiment-log.md](experiments/experiment-log.md) | 시도했다 바꾼 것들 (3D 렌더링, 카메라 협상, FPS, 한글 이슈 등) | 개발자 (**같은 실험 반복 방지**) |
| [meetings/](meetings/) | [meeting-agenda-and-questions.md](meetings/meeting-agenda-and-questions.md) | ONLAB×우송대 협력과제 회의 안건 (국문) | 협의체 |
| | [meeting-agenda-and-questions-en.md](meetings/meeting-agenda-and-questions-en.md) | 위 문서 영문판 | 협의체 |

## 빠른 시작

```bash
pip install -r requirements.txt
python main.py --source testdata/tree_balance.jpg --windowed   # 카메라 없이 확인
python main.py                                                  # 카메라 0번, 전체화면
```

루트의 [README.md](../README.md)(전체 소개), [SETUP.md](../SETUP.md)(환경 구성), [CLAUDE.md](../CLAUDE.md)(AI 어시스턴트용 요약)도 참고.

## 문서 작성 규칙

- 새 문서는 위 폴더 주제에 맞춰 배치하고 이 표에 한 줄 추가 (파일·폴더명은 영어 kebab-case)
- 시도했다가 폐기/전환한 내용은 반드시 [experiments/experiment-log.md](experiments/experiment-log.md)에 남길 것
- 콘텐츠 아이디어·기획 논의는 content/ 폴더에

---

# English

**OnLab** is a kiosk **AI motion-game** app built on MediaPipe pose estimation. A camera estimates the user's skeleton (33 keypoints) and drives several games: a stretching course (accuracy + hold scoring with a flexibility report), a 2-player battle, a reaction test, a high jump, and push-ups. It ships with per-game leaderboards, an admin screen, and an attract mode. Two implementations — desktop (Python + PySide6) and web (TypeScript + WASM, stretching only) — share the scoring logic.

## Document map

| Folder | Document | Contents | Audience |
|---|---|---|---|
| [dev/](dev/) | [architecture.md](dev/architecture.md) | Module structure, pipeline, verification methods, rules to follow | Developers (read first when onboarding) |
| | [game-structure-revamp-2026-07.md](dev/game-structure-revamp-2026-07.md) | Work log for the game-selection home + 3 new mini-games (reaction / jump / push-ups) | Developers |
| | [srs-template.md](dev/srs-template.md) | SRS template — functional / non-functional / AI requirements | Planning · dev |
| [content/](content/) | [idea-feasibility.md](content/idea-feasibility.md) | Event-content idea triage + implementation direction for the top candidates | Planning · dev |
| | [game-references.md](content/game-references.md) | Research on engagement design (honeypot effect, attract loops, feedback — sources verified) | Planning · dev |
| | [engagement-improvements.md](content/engagement-improvements.md) | Research-backed improvement priorities + roadmap (top pick: attract-mode live mirror) | Planning · dev · ops |
| [deploy/](deploy/) | [build-guide.md](deploy/build-guide.md) | GitHub Actions / PyInstaller builds, kiosk install & autostart, troubleshooting | Ops · dev |
| | [event-checklist.md](deploy/event-checklist.md) | On-site operations guide — placement, demos, talk tracks (research-backed) | Ops |
| [experiments/](experiments/) | [experiment-log.md](experiments/experiment-log.md) | Things we tried and changed (3D rendering, camera negotiation, FPS, Hangul issues…) | Developers (**prevents repeating failed experiments**) |
| [meetings/](meetings/) | [meeting-agenda-and-questions.md](meetings/meeting-agenda-and-questions.md) | ONLAB × Woosong University project meeting agenda (Korean) | Steering group |
| | [meeting-agenda-and-questions-en.md](meetings/meeting-agenda-and-questions-en.md) | English version of the above | Steering group |

## Quick start

```bash
pip install -r requirements.txt
python main.py --source testdata/tree_balance.jpg --windowed   # try without a camera
python main.py                                                  # camera 0, fullscreen
```

See also the repo-root [README.md](../README.md) (project intro), [SETUP.md](../SETUP.md) (environment setup), and [CLAUDE.md](../CLAUDE.md) (summary for AI assistants).

Note: most documents are written in Korean; file and folder names are English. The kiosk UI itself is bilingual (Korean primary, small English subtitles).

## Writing rules

- Place new documents in the matching folder above and add a row to this table (file/folder names in English kebab-case)
- Anything tried and then abandoned/changed **must** be recorded in [experiments/experiment-log.md](experiments/experiment-log.md)
- Content ideas and planning discussions go in content/
