# ONLAB × Woosong University Collaboration — Meeting Agenda & Question List

> Authored from: **ONLAB (host)** → for Woosong University (development partner)
> Purpose: Confirm scope, system, roles, and schedule for the kiosk-based pose-estimation (skeleton) interaction project
> Legend: `▢ FILL/DECIDE` = ONLAB to finalize, `▶ PROPOSAL` = ONLAB proposal, `▷ DISCUSS w/ Woosong` = to agree/request with Woosong, `※` = note
>
> ※ Recommended inference backbone: **MediaPipe** (prototype-validated; licensing, real-time on CPU, faster development).
>   OpenPose is compared as an alternative in 2.2. Prototype: MediaPipe + Python (PySide6) / Web (TS + WASM).

---

## 1. ONLAB Company Introduction

- `▢ FILL/DECIDE` Company overview (founding, business areas, key clients/references)
- `▢ FILL/DECIDE` Solutions / services
  - Kiosk-based service lineup (hardware specs, install environments, operating cases)
  - Prior vision/AI interaction experience (pose estimation, gesture, touch)
- `▢ FILL/DECIDE` Assets ONLAB can provide for this project (kiosk HW, camera, Jetson, content IP, branding)

---

## 2. Project Introduction

### 2.1 Use Scenarios / Applications / Content

**Core definition (to agree):** "Which user / in which environment / gains what experience / through what flow"

- `▢ FILL/DECIDE` Target users (age, purpose), install environment (expo, event, store, gym), session length
- `▢ FILL/DECIDE` Concurrent users (single / multi), waiting & transition flow
- `▢ FILL/DECIDE` Content priority: educational / entertainment / event-experience mix

**▶ PROPOSAL — 4 content types + standard user scenario**

Common flow: `Idle (person detected) → name/mode select → countdown → perform/evaluate → result/score → leaderboard/share`

| Content | Type | Example user scenario | Judging method |
|---------|------|----------------------|----------------|
| **Body Quiz** | Fun/Edu | "Raise right hand, lower left hand" → answer by posture | Joint position/angle rule matching |
| **Motion Game** | Fun | Pop balloons on screen with fingertips | Wrist/fingertip coordinate hitbox |
| **Exercise Coaching** | Edu | Squat/stretch analysis → accuracy & correction guide | **Joint-angle scoring** (current prototype) |
| **Dance / Flexibility Battle** | Fun | Two players simultaneously → similarity/score compare, winner | Pose-vector similarity / angle score + **2-player versus** (implemented) |

**※ Already implemented (prototype) — ready to demo now**
- Flexibility/stretch scoring (forward bend, side bend, overhead reach, T-pose, one-leg balance)
- Hold-time detection, accuracy gauge, **flexibility report (joint angles, grade, left/right asymmetry)**
- **Difficulty/theme courses**, **leaderboard**, voice/sound guidance, target-pose guide, admin screen
- **2-player real-time versus** (left/right players, split screen, winner)

`▶ PROPOSAL` Build the 4 types as "common interaction engine + content plugins" so adding content is easy.

### 2.2 System Configuration

| Item | Spec (to confirm) | ▶ Proposal/Note |
|------|-------------------|-----------------|
| **Camera** | `▢` resolution / FPS / FOV | Wide angle (≥90°), ≥1080p·30fps for full-body capture |
| **Compute** | `▢` Jetson Orin NX (module/RAM, 8GB vs 16GB) | MediaPipe runs real-time on CPU → headroom; GPU delegate on Jetson |
| **Display** | `▢` size / resolution / **touch?** | Kiosks often portrait → affects layout |
| **Speaker** | `▢` used? | Needed for voice (TTS) & sound effects |
| **OS** | `▢` Ubuntu version (Jetson = JetPack L4T) | JetPack version drives CUDA/drivers |
| **Inference backbone** | `▶` **MediaPipe Pose (recommended)** / OpenPose (alt) | See comparison below |
| **Language** | `▢` C++ / Python boundary | Python-only for dev speed (prototype); optimize hotspots in C++ if needed |
| **Framework** | `▢` PySide6/Qt (rec.) / Unity | Prototype = PySide6 (desktop) + Web; Unity if strong 3D/FX |

**Backbone comparison (recommended: MediaPipe)**

| | **MediaPipe Pose** (rec.) | OpenPose (alt) |
|---|---|---|
| Real-time | Real-time on CPU (~30fps), headroom on Jetson | Requires GPU; needs tuning on Jetson |
| License | Apache-2.0 (free commercial use) | Commercial licensing concerns |
| 3D coords | Provided (world landmarks) → better angle scoring | Mostly 2D |
| Multi-person | numPoses config (versus implemented) | Strong in crowded scenes |
| Maturity | Prototype-validated | Complex build/dependencies |

**Key questions**
- `▷ DISCUSS w/ Woosong` Accept **MediaPipe recommendation**? (Re-compare if OpenPose is specifically required)
- `▢` Multi-person requirement (versus) / crowded environment? → affects backbone/model choice
- `▢` Final deliverable form: single kiosk app / web deployment / both (prototype has both)

### 2.3 AI Performance Evaluation

`▶ PROPOSAL — evaluation metrics (to agree)`
- **Keypoint accuracy**: PCK / MPJPE (reference dataset or self-captured set)
- **Real-time**: FPS on Jetson, frame latency (ms) — e.g., target ≥15fps, ≤100ms
- **Robustness**: lighting, distance, clothing, occlusion, multi-person
- **Interaction accuracy**: gesture/pose decision accuracy, false-positive rate
- **Scoring validity**: correlation vs expert labels, repeatability (score variance for same pose)
- `▢` Acceptance criteria and who provides evaluation data

### 2.4 Detailed Development Schedule (by deliverable)

| Phase | Deliverable | Timing (draft) |
|-------|-------------|----------------|
| Requirements | **System Requirements Specification** (functional/non-functional/performance) | `▢` |
| Design | **Design document** (architecture, pipeline, content spec, UI/UX) | `▢` |
| Implementation | Interaction engine + 4 content types, admin tools | `▢` |
| Integration/Test | Hardware integration, performance/stability tests | `▢` |
| Field validation | Real install-environment validation, feedback | `▢` |

`▶ PROPOSAL` Pipeline/engine/prototype already exist → after finalizing spec/design, focus on porting/optimizing to the target stack.

---

## 3. Roles & Responsibilities

### 3.1 Expectations of Woosong (development team)

Develop/optimize the full pipeline:

```
Camera → Frame Acquisition → Pose Estimation (MediaPipe/OpenPose) → Skeleton
      → Gesture/Pose Recognition → Interaction Engine → Application → Display
```

- Dev environment setup (Jetson JetPack, pose runtime, camera integration, framework)
- Interaction engine (pose/gesture decision & scoring) and content implementation
- Performance optimization (TensorRT, etc.) and stabilization
- `▢` Clear scope boundary of deliverables (what exactly students own)

### 3.2 Expectations of Woosong students

- `▷ DISCUSS w/ Woosong` Number of participants / majors / level, engagement period (semester, hours/week)
- `▷ DISCUSS w/ Woosong` Role split (Vision/AI, App/UI, Integration/QA)
- `▶ PROPOSAL` Regular deliverable submission (weekly/biweekly reports), version control (Git)

### 3.3 Support for Woosong students

- `▢` Hardware loan (Jetson, camera, kiosk/display)
- `▢` Dev environment/licenses, datasets, mentoring/industry review
- `▢` Stipend/scholarship/internship, industry-academic agreement & IP ownership

---

## 4. Execution Plan

- **4.1** Monthly progress review (`▢` date/format: on/offline, demo included?)
- **4.2** Milestones
  - **November** interim presentation
  - **January 2027** final presentation
- `▶ PROPOSAL` Working demo + metrics report each review; one rehearsal before presentations

---

## Appendix. 5 Must-Decide Items

1. Backbone decision (**MediaPipe recommended** vs OpenPose) + multi-person requirement
2. Hardware specs (camera, Jetson, display/touch, speaker)
3. Content priority (of the 4) and first-demo scope
4. Deliverable/role boundaries (engine/content/integration) and student support (HW/IP/compensation)
5. Schedule: spec/design deadlines and November interim demo scope
