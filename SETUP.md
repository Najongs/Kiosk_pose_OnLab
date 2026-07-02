# OnLab 실행 요구사항 & 설치 가이드

앱은 두 가지입니다. 목적에 맞게 하나만 설치해도 됩니다.

| | 데스크톱 앱 (Python) | 웹앱 (브라우저) |
|---|---|---|
| 추론 위치 | 키오스크 로컬 | 사용자 브라우저(WASM) |
| 적합 | 물리 키오스크·오프라인 | 사용자 기기·배포·공유 |
| 폴더 | 루트 (`main.py`) | `web/` |

---

## 1) 데스크톱 앱 (Python / PySide6)

### 요구사항
- **Python 3.10+** (검증: 3.12, conda env `OnLab`)
- pip 패키지: `requirements.txt` (mediapipe, opencv-python-headless, numpy, pillow, PySide6)
- **포즈 모델 번들**: `models/pose_landmarker_full.task` (약 9.4MB)
- **한글 폰트**: Noto Sans CJK KR 또는 나눔고딕
- (선택) **espeak-ng**: 음성 안내용. 없으면 무음
- 실행 시: 웹캠 (없으면 이미지/영상으로 테스트)

### 설치
```bash
conda activate OnLab            # 또는  python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 시스템 패키지 (Ubuntu 기준)
sudo apt install fonts-noto-cjk         # 한글 폰트 (필수)
sudo apt install espeak-ng              # 음성 안내 (선택)

# 포즈 모델 (최초 1회)
mkdir -p models
curl -L -o models/pose_landmarker_full.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
```

### 실행
```bash
python main.py                              # 카메라 0번, 전체화면 (홈→세션)
python main.py --source testdata/ --windowed   # 카메라 없이 이미지로 테스트
python main.py --source video.mp4           # 영상 파일로
```
키: `Esc/Q` 종료·뒤로, `F` 전체화면 토글. 관리자 화면은 홈 우상단 ⚙.

### 디스플레이 없는 서버에서 확인
```bash
QT_QPA_PLATFORM=offscreen python tools/verify_ui.py   # 홈/관리자/세션 → out/ui_py/*.png
QT_QPA_PLATFORM=offscreen python main.py --source testdata/ --windowed  # ssh -X / xvfb-run 대안
```

---

## 2) 웹앱 (Vite + TypeScript + MediaPipe WASM)

### 요구사항
- **Node.js 18+** (검증: 22) & npm
- 모델·WASM·포즈 JSON 은 이미 `web/public/` 에 포함 (외부 CDN 불필요)
- 카메라 권한은 **HTTPS 또는 localhost** 에서만 허용

### 설치·실행·배포
```bash
cd web
npm install
npm run dev        # http://localhost:5173 (카메라 있는 기기 브라우저로)
npm test           # 파이썬 대비 채점 패리티 테스트
npm run build      # dist/ 정적 산출물 → Netlify/Vercel/nginx 등에 배포 (HTTPS 필수)
```

### 헤드리스 검증 (개발용, 선택)
```bash
npx playwright install chromium         # 최초 1회
npm run build && npm run preview -- --port 4173 &
node scripts/shoot.mjs                  # 홈/리더보드/관리자 스크린샷 → shots/
node scripts/smoke.mjs                  # 가짜 웹캠으로 세션 전체 스모크
```

### 키오스크로 쓰기
```bash
chromium --kiosk --use-fake-ui-for-media-stream https://<배포주소>
```

---

## 데이터·설정 파일 위치
- 데스크톱: `config/app_config.json`(설정), `config/refs.json`(목표자세), `data/leaderboard.json`(랭킹)
- 웹: 브라우저 `localStorage` (`onlab.config`, `onlab.refs`, `onlab.leaderboard`)
- 공통: `config/poses/*.json` (자세 정의 — 두 앱이 동일 스키마 공유)
