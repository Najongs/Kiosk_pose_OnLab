# OnLab Web — 브라우저(WASM) 유연성 테스트

사용자가 **자기 기기(폰/노트북/키오스크 브라우저)** 에서 접속하면, 포즈추정이
**브라우저 안에서**(`@mediapipe/tasks-vision`, WASM/WebGL) 실행된다. 영상은
기기 밖으로 나가지 않으며 서버는 정적 호스팅만 담당한다.

파이썬 앱과 **자세 정의 JSON(`public/poses/`) · 채점 로직을 공유**한다
(로직은 TS로 포팅, `test/parity.test.ts`가 파이썬과 점수 일치를 검증).

**기능**: 홈+이름 입력, 리더보드, 음성/효과음, 목표 자세 가이드, 관리자 화면,
**난이도/테마 코스**(`courses.ts`), **유연성 리포트+좌우 비대칭**(`report.ts`),
**2인 실시간 대결**(`versus.ts`, numPoses=2, 분할 HUD).

## 개발 / 빌드

```bash
cd web
npm install
npm run dev        # http://localhost:5173 (개발 서버)
npm test           # 파이썬 대비 채점 패리티 테스트
npm run build      # dist/ 정적 산출물 생성
npm run preview    # 빌드 결과 로컬 서빙
```

> `getUserMedia`(카메라)는 **HTTPS 또는 localhost**에서만 동작한다.
> 개발 서버는 localhost라 OK. 다른 기기에서 테스트하려면 HTTPS 필요.

## 배포 (정적 호스팅)

`npm run build` 후 `dist/` 를 그대로 올리면 된다.

- Netlify/Vercel/Cloudflare Pages: `dist/` 를 배포(빌드 명령 `npm run build`,
  퍼블리시 디렉토리 `dist`).
- nginx/S3+CloudFront 등 임의 정적 서버도 가능. **HTTPS 필수**(카메라 권한).
- 모델(`.task`, 9.4MB)과 WASM 런타임을 정적 자산으로 포함하므로 **오프라인/사내망**
  배포도 가능(외부 CDN 불필요).

## 키오스크로 쓰려면

키오스크 장비에서 Chromium 을 kiosk 모드로 이 URL을 띄우면 그대로 키오스크가 된다:

```bash
chromium --kiosk --use-fake-ui-for-media-stream https://<배포주소>
```

## 구조

```
src/
  keypoints.ts      33 키포인트 인덱스/골격 (파이썬과 동일)
  geometry.ts       각도/기울기
  poseDef.ts        자세 정의 타입 + 로더(fetch)
  scorer.ts         각도 기반 채점 (파이썬 core/scorer.py 포팅)
  hold.ts           유지시간 판정
  session.ts        세션 상태머신
  poseEstimator.ts  MediaPipe PoseLandmarker(WASM) 래퍼 + 주대상 선택
  renderer.ts       canvas 스켈레톤 + DOM HUD
  main.ts           카메라→추정→세션→렌더 루프
public/
  models/pose_landmarker_full.task
  wasm/             MediaPipe WASM 런타임
  poses/*.json      자세 정의(파이썬과 공유) + index.json
test/parity.test.ts 파이썬 대비 채점 일치 검증
```

## 검증 상태

- ✅ 채점 로직 파이썬 패리티 (4개 케이스, 오차 <0.01)
- ✅ 타입체크 + 프로덕션 빌드
- ✅ 모든 자산(JS/모델/WASM/포즈) 서빙 200
- ⏳ 실제 브라우저 웹캠 추론: 카메라 있는 기기에서 확인 필요
  (또는 헤드리스 Chromium + fake video 스모크 테스트 추가 가능)
```
