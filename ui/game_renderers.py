"""미니게임 화면 합성 (Qt 비의존) — renderer.py 와 같은 계약.

각 compose_* 는 (표시 해상도 BGR 프레임, 표시 좌표로 스케일된 primary,
게임 State, anim_t) 를 받아 완성 화면 한 장을 반환한다.
룩은 기존 스트레칭 HUD 와 통일: 네온 스켈레톤 + 반투명 패널 + 컨페티/등급.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from core.drawing import (
    TextItem,
    draw_skeleton,
    draw_texts,
    gauge_bar,
    panel,
    text_width,
    translucent_rect,
)
from core.games.jump import JState, JumpState
from core.i18n import en
from core.games.pushup import PState, PushupState
from core.games.reaction import ReactionState, RState
from core.pose_estimator import PersonPose
from ui.hud import (
    SUB_COLOR,
    burst_rays,
    confetti,
    corner_brackets,
    draw_popups,
    expanding_rings,
    grade_of,
    msg_pill,
    next_grade_gap,
    progress_dots,
    stage_light as _stage_light,
    top_accent,
)

ACCENT = (160, 231, 127)      # 민트 (BGR)
GOLD = (60, 200, 255)
WARN_RGB = (255, 140, 140)


def _top_bar(frame: np.ndarray, texts: list[TextItem], title: str,
             sub: str = "", anim_t: float | None = None) -> None:
    h, w = frame.shape[:2]
    translucent_rect(frame, 0, 0, w, int(h * 0.11), color=(14, 16, 26), alpha=0.62)
    top_accent(frame, int(h * 0.11), anim_t)
    big = max(26, h // 20)
    title_en = en(title)
    ty = int(h * 0.047) if title_en else int(h * 0.055)
    texts.append(TextItem(title, (24, ty), big, (255, 255, 255), anchor="lm"))
    if title_en:  # 제목 아래 영어 병기(작게) — 상단바 높이는 그대로
        texts.append(TextItem(title_en, (26, int(h * 0.089)),
                              max(13, h // 52), SUB_COLOR, anchor="lm", stroke=1))
    if sub:  # 제목 폭을 재서 겹치지 않게 배치
        sx = max(int(w * 0.42), 24 + text_width(title, big) + 32)
        texts.append(TextItem(sub, (sx, int(h * 0.055)),
                              max(20, h // 28), (200, 220, 255), anchor="lm"))


def _done_panel(frame: np.ndarray, texts: list[TextItem], headline: str,
                score: float, lines: list[str], anim_t: float | None) -> None:
    h, w = frame.shape[:2]
    translucent_rect(frame, 0, 0, w, h, alpha=0.66)
    burst_rays(frame, w // 2, int(h * 0.46), anim_t,
               color=GOLD if score >= 85 else ACCENT)
    confetti(frame, anim_t)
    # 영어 병기 줄 수에 따라 패널 바닥을 늘린다 (겹침·넘침 방지)
    fs_est = max(20, h // 26)
    est = int(h * 0.575)
    for line in lines + ["한 번 더?"]:
        est += int(fs_est * (1.8 if en(line) else 1.5))
    panel(frame, int(w * 0.16), int(h * 0.22), int(w * 0.84),
          max(int(h * 0.80), min(int(h * 0.92), est + int(fs_est * 0.6))),
          radius=24, color=(12, 14, 24), alpha=0.72,
          border=ACCENT, border_thickness=2)
    texts.append(TextItem(headline, (w // 2, int(h * 0.305)), max(34, h // 14),
                          (120, 255, 140), anchor="mm"))
    head_en = en(headline)
    if head_en:
        texts.append(TextItem(head_en, (w // 2, int(h * 0.355)),
                              max(15, h // 42), SUB_COLOR, anchor="mm", stroke=1))
    grade, grade_rgb = grade_of(score)
    score_fs = max(60, h // 8)
    score_txt = f"{score:.0f}점"
    texts.append(TextItem(score_txt, (w // 2, int(h * 0.46)),
                          score_fs, (255, 255, 255), anchor="mm", stroke=5))
    half = text_width(score_txt, score_fs) // 2  # 점수 폭을 재서 등급을 우측에
    texts.append(TextItem(grade, (w // 2 + half + int(w * 0.05), int(h * 0.45)),
                          max(50, h // 10), grade_rgb, anchor="mm", stroke=5))
    fs = max(20, h // 26)
    ss = max(13, int(fs * 0.62))
    y = int(h * 0.575)
    for line in lines:
        texts.append(TextItem(line, (w // 2, y), fs, (220, 235, 255), anchor="mm"))
        sub = en(line)
        if sub:  # 영어 병기 한 줄 (작게) — 줄 간격을 좁혀 패널 안에 수렴
            y += int(fs * 1.02)
            texts.append(TextItem(sub, (w // 2, y), ss, SUB_COLOR,
                                  anchor="mm", stroke=1))
            y += int(fs * 0.78)
        else:
            y += int(fs * 1.5)
    gap = next_grade_gap(score)  # 근접 목표 — 재도전 유도
    if gap:
        line = f"한 번 더?  {gap}"
        texts.append(TextItem(line, (w // 2, y), fs, (255, 220, 130), anchor="mm"))
        sub = en(line)
        if sub:
            texts.append(TextItem(sub, (w // 2, y + int(fs * 1.02)), ss,
                                  SUB_COLOR, anchor="mm", stroke=1))


def compose_reaction(frame: np.ndarray, primary: PersonPose | None,
                     state: ReactionState, anim_t: float | None = None,
                     popups: list[dict] | None = None) -> np.ndarray:
    h, w = frame.shape[:2]
    texts: list[TextItem] = []
    _stage_light(frame, primary,
                 state.state in (RState.WAIT, RState.SIGNAL))
    if state.state in (RState.WAIT, RState.SIGNAL):
        corner_brackets(frame, GOLD if state.signal_on else ACCENT, anim_t)
    if primary is not None:
        # 테마 색: 대기=민트, 신호=골드 (게임 정체성 + 상태가 색으로 읽힘)
        c = GOLD if state.signal_on else (127, 231, 160)
        draw_skeleton(frame, primary, color=c,
                      joint_color=(90, 220, 255) if state.signal_on
                      else (0, 160, 255))

    cur = min(state.round_index + 1, state.round_total)
    _top_bar(frame, texts, "반응속도 테스트", f"라운드 {cur}/{state.round_total}",
             anim_t)
    progress_dots(frame, state.round_index, state.round_total, w, h)
    if state.best_ms is not None and state.state != RState.DONE:
        texts.append(TextItem(f"최고 {state.best_ms:.0f}ms",
                              (24, int(h * 0.16)), max(20, h // 28),
                              (255, 235, 180), anchor="lm"))

    if state.state == RState.SIGNAL:
        # 확산 링 + 화면 테두리 플래시 + 큰 신호 텍스트 (뜨는 순간 팝)
        if state.signal_age is not None:
            expanding_rings(frame, w // 2, int(h * 0.42), state.signal_age,
                            color=GOLD)
        t = max(6, h // 40)
        cv2.rectangle(frame, (t // 2, t // 2), (w - t // 2, h - t // 2),
                      GOLD, t, cv2.LINE_AA)
        pop = 1.0
        if state.signal_age is not None and state.signal_age < 0.25:
            pop = 1.35 - 1.4 * state.signal_age  # 크게 떴다가 빠르게 안착
        texts.append(TextItem("지금!", (w // 2, int(h * 0.42)),
                              int(max(90, h // 5) * pop),
                              (255, 230, 90), anchor="mm", stroke=6))
        msg_pill(frame, texts, "손을 번쩍 드세요!", int(h * 0.66),
                 max(26, h // 20))
    elif state.state == RState.WAIT:
        # 긴장 유도: 화면을 살짝 어둡게 + 숨쉬는 대기 점
        translucent_rect(frame, 0, 0, w, h, color=(8, 9, 14), alpha=0.25)
        if anim_t is not None:
            k = int(anim_t * 2.5) % 3 + 1
            texts.append(TextItem("●" * k, (w // 2, int(h * 0.42)),
                                  max(30, h // 18), (150, 165, 195),
                                  anchor="mm"))
        msg_pill(frame, texts, state.message, int(h * 0.80), max(24, h // 22))
    elif state.state == RState.REST and (state.false_start or state.timed_out):
        msg_pill(frame, texts, state.message, int(h * 0.48), max(30, h // 16),
                 WARN_RGB)
    elif state.state == RState.REST and state.last_ms is not None:
        texts.append(TextItem(f"{state.last_ms:.0f}", (w // 2, int(h * 0.44)),
                              max(90, h // 5), (255, 255, 255), anchor="mm",
                              stroke=6))
        texts.append(TextItem("ms", (w // 2, int(h * 0.58)), max(30, h // 18),
                              (200, 220, 255), anchor="mm"))
    elif state.state == RState.DONE:
        avg = f"{state.avg_ms:.0f}ms" if state.avg_ms is not None else "-"
        best = f"{state.best_ms:.0f}ms" if state.best_ms is not None else "-"
        lines = [f"평균 {avg}   ·   최고 {best}"]
        if state.false_starts:
            lines.append(f"부정 출발 {state.false_starts}회")
        _done_panel(frame, texts, "반응속도 결과", state.score or 0.0, lines,
                    anim_t)
    else:
        msg_pill(frame, texts, state.message, int(h * 0.80), max(24, h // 22))

    if popups and anim_t is not None:
        draw_popups(frame, texts, popups, anim_t)
    return draw_texts(frame, texts)


def compose_jump(frame: np.ndarray, primary: PersonPose | None,
                 state: JumpState, anim_t: float | None = None,
                 popups: list[dict] | None = None) -> np.ndarray:
    h, w = frame.shape[:2]
    texts: list[TextItem] = []
    _stage_light(frame, primary,
                 state.state in (JState.READY, JState.JUMP))
    if state.state in (JState.READY, JState.JUMP):
        corner_brackets(frame, ACCENT, anim_t)
    if primary is not None:
        # 테마 색: 하늘색 (홈 카드 액센트 #4aa8ff 와 일치)
        draw_skeleton(frame, primary, color=(255, 168, 74),
                      joint_color=(255, 220, 160))

    cur = min(state.attempt_index + 1, state.attempt_total)
    _top_bar(frame, texts, "높이뛰기", f"시도 {cur}/{state.attempt_total}", anim_t)
    progress_dots(frame, state.attempt_index, state.attempt_total, w, h)

    # 기준선(어둡게) + 목표선(액센트, '공' 표시) — 게임 좌표는 표시 프레임 기준
    if state.baseline_head_y is not None and state.state != JState.DONE:
        yb = int(state.baseline_head_y)
        for x0 in range(0, w, 30):
            cv2.line(frame, (x0, yb), (min(w, x0 + 15), yb), (110, 116, 138), 2,
                     cv2.LINE_AA)
    if state.target_line_y is not None and state.state in (
            JState.READY, JState.JUMP, JState.REST):
        yt = int(state.target_line_y)
        # 목표선 호흡 펄스 + 매달린 공이 살짝 까딱거림
        pulse = 0.5 + 0.5 * math.sin((anim_t or 0) * 3.0)
        line_c = tuple(int(c * (0.7 + 0.3 * pulse)) for c in ACCENT)
        cv2.line(frame, (0, yt), (w, yt), line_c, 3, cv2.LINE_AA)
        r = max(10, h // 40)
        bob = int(math.sin((anim_t or 0) * 2.2) * r * 0.25)
        bx, by = w // 2, yt - r + bob
        cv2.line(frame, (bx, 0), (bx, by - r), (90, 96, 118), 2, cv2.LINE_AA)  # 공 줄
        cv2.circle(frame, (bx, by), r, (80, 200, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, (bx - r // 3, by - r // 3), max(2, r // 3),
                   (200, 240, 255), -1, cv2.LINE_AA)  # 하이라이트
        cv2.circle(frame, (bx, by), r, (30, 120, 200), 2, cv2.LINE_AA)
        texts.append(TextItem(f"목표 {state.target_cm:.0f}cm", (16, yt - 10),
                              max(18, h // 32), (160, 255, 200), anchor="lb"))
    # 점프 중: 상승 스피드 라인 + 실시간 높이 표시
    if state.state == JState.JUMP and state.current_head_y is not None:
        hy_i = int(state.current_head_y)
        for k in range(6):
            x = int(w * (0.12 + 0.76 * ((k * 0.618) % 1.0)))
            y0 = (hy_i + 60 + int(((anim_t or 0) * 500 + k * 90) % 240))
            if y0 < h:
                cv2.line(frame, (x, y0), (x, min(h, y0 + 34)), (120, 200, 160), 2,
                         cv2.LINE_AA)
        if state.baseline_head_y is not None and state.cm_per_px:
            live = max(0.0, (state.baseline_head_y - state.current_head_y)
                       * state.cm_per_px)
            texts.append(TextItem(f"{live:.0f}cm", (w // 2, max(40, hy_i - 40)),
                                  max(30, h // 16), (160, 255, 200),
                                  anchor="mm", stroke=4))

    if state.best_cm is not None and state.state != JState.DONE:
        texts.append(TextItem(f"최고 약 {state.best_cm:.0f}cm",
                              (24, int(h * 0.16)), max(20, h // 28),
                              (255, 235, 180), anchor="lm"))

    if state.state == JState.CALIBRATE:
        gx, gw_ = int(w * 0.3), int(w * 0.4)
        gy, gh_ = int(h * 0.62), max(16, h // 32)
        panel(frame, gx - 12, gy - 12, gx + gw_ + 12, gy + gh_ + 12, radius=10,
              color=(14, 16, 26), alpha=0.55)
        gauge_bar(frame, gx, gy, gw_, gh_, state.calib_progress, fg=ACCENT,
                  anim_t=anim_t)
        msg_pill(frame, texts, state.message, int(h * 0.54), max(24, h // 22))
    elif state.state == JState.REST and state.last_cm is not None:
        texts.append(TextItem(f"약 {state.last_cm:.0f}cm",
                              (w // 2, int(h * 0.44)), max(70, h // 6),
                              (255, 255, 255), anchor="mm", stroke=6))
    elif state.state == JState.DONE:
        best = state.best_cm or 0.0
        tries = "  ·  ".join(f"{c:.0f}cm" for c in state.attempts_cm) or "-"
        _done_panel(frame, texts, "높이뛰기 결과", state.score or 0.0,
                    [f"최고 약 {best:.0f}cm", f"기록: {tries}",
                     "* 단일 카메라 근사치"], anim_t)
    else:
        msg_pill(frame, texts, state.message, int(h * 0.80), max(24, h // 22))

    if popups and anim_t is not None:
        draw_popups(frame, texts, popups, anim_t)
    return draw_texts(frame, texts)


def compose_pushup(frame: np.ndarray, primary: PersonPose | None,
                   state: PushupState, anim_t: float | None = None,
                   popups: list[dict] | None = None) -> np.ndarray:
    h, w = frame.shape[:2]
    texts: list[TextItem] = []
    _stage_light(frame, primary, state.state == PState.COUNTING)
    if state.state == PState.COUNTING:
        corner_brackets(frame, ACCENT if state.posture_ok else (60, 80, 235),
                        anim_t)
    if primary is not None:
        # 테마 색: 주황 (홈 카드 액센트 #ff8a4a) — 자세 무너지면 붉게
        draw_skeleton(frame, primary,
                      color=(74, 138, 255) if state.posture_ok else (60, 80, 235),
                      joint_color=(120, 200, 255))

    low_time = (state.mode == "timed" and state.time_remaining is not None
                and 0 < state.time_remaining <= 5.0
                and state.state == PState.COUNTING)
    sub = (f"남은 시간 {state.time_remaining:.0f}s"
           if state.mode == "timed" and state.time_remaining is not None
           else f"목표 {state.target_reps}개")
    _top_bar(frame, texts, "팔굽혀펴기", sub if not low_time else "", anim_t)
    if low_time:  # 마지막 5초 — 크고 붉게 깜빡이는 카운트다운
        k = 0.5 + 0.5 * math.sin((anim_t or 0) * 8.0)
        texts.append(TextItem(f"남은 시간 {state.time_remaining:.0f}s !",
                              (int(w * 0.42), int(h * 0.055)),
                              max(24, h // 22),
                              (255, int(120 + 100 * k), int(120 + 100 * k)),
                              anchor="lm"))

    if state.state == PState.IDLE:
        msg_pill(frame, texts, state.message, int(h * 0.5), max(26, h // 20))
        texts.append(TextItem("측면(옆모습)이 잘 보이면 더 정확해요",
                              (w // 2, int(h * 0.60)), max(18, h // 32),
                              (170, 185, 210), anchor="mm"))
        texts.append(TextItem(en("측면(옆모습)이 잘 보이면 더 정확해요") or "",
                              (w // 2, int(h * 0.645)), max(13, h // 48),
                              SUB_COLOR, anchor="mm", stroke=1))
    elif state.state == PState.COUNTING:
        # 큰 개수 카운터 (우측) — 내려간(down) 동안 테두리가 골드로 달아오름
        down = state.phase == "down"
        panel(frame, int(w * 0.72), int(h * 0.30), int(w * 0.97), int(h * 0.56),
              radius=18, color=(12, 14, 24), alpha=0.6,
              border=GOLD if down else ACCENT, border_thickness=3 if down else 2)
        texts.append(TextItem(str(state.reps), (int(w * 0.845), int(h * 0.41)),
                              int(max(70, h // 6) * (1.08 if down else 1.0)),
                              (255, 230, 140) if down else (255, 255, 255),
                              anchor="mm", stroke=5))
        texts.append(TextItem("개 · reps", (int(w * 0.845), int(h * 0.52)),
                              max(20, h // 28), (200, 220, 255), anchor="mm"))
        # 팔꿈치 굽힘 게이지 (하단): up_angle→down_angle 구간을 0→1 로.
        # 임계 근처에서 색이 골드로 변해 "여기까지 내려가면 인정"을 보여준다
        if state.elbow_angle is not None:
            span = max(1e-6, state.up_angle - state.down_angle)
            ratio = max(0.0, min(1.0, (state.up_angle - state.elbow_angle) / span))
            gx, gy = int(w * 0.2), int(h * 0.88)
            gw_, gh_ = int(w * 0.6), max(18, h // 34)
            panel(frame, gx - int(w * 0.055), gy - 10, gx + gw_ + 14,
                  gy + gh_ + 10, radius=12, color=(14, 16, 26), alpha=0.5)
            fg = GOLD if ratio >= 0.97 else (230, 180, 40)
            gauge_bar(frame, gx, gy, gw_, gh_, ratio, fg=fg, pass_ratio=0.97,
                      anim_t=anim_t)
            texts.append(TextItem("굽힘", (gx - 12, gy + gh_ // 2),
                                  max(18, h // 34), (255, 235, 180), anchor="rm"))
        if not state.posture_ok and state.posture_msg:
            msg_pill(frame, texts, state.posture_msg, int(h * 0.72),
                     max(26, h // 20), WARN_RGB)
    elif state.state == PState.DONE:
        q = int((state.quality or 0) * 100)
        _done_panel(frame, texts, "팔굽혀펴기 결과", state.score or 0.0,
                    [f"{state.reps}개 (바른 자세 {state.good_reps}개)",
                     f"자세 품질 {q}%"], anim_t)

    if popups and anim_t is not None:
        draw_popups(frame, texts, popups, anim_t)
    return draw_texts(frame, texts)
