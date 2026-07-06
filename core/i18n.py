"""한국어 UI 문구의 영어 보조 표기 (bilingual subtitle).

키오스크는 언어 전환 버튼 없이 **한국어(주) + 영어(작은 보조)** 를 함께
표시한다 — 행사장에서 외국인 방문객도 조작 없이 이해할 수 있도록.

- 정적 문구: EN 사전에서 정확 일치로 찾는다.
- 숫자·자세명이 들어간 동적 문구: _PATTERNS 정규식으로 변환한다
  (캡처된 자세명 등은 다시 사전을 거쳐 번역).
- en() 이 None 이면 보조 표기를 그리지 않는다 — 숫자·단위 위주 문구처럼
  언어 없이도 이해되는 것은 등록하지 않아 화면을 어지럽히지 않는다.

새 사용자 문구를 추가할 때는 여기에도 짝을 등록할 것.
"""

from __future__ import annotations

import re
from typing import Callable

# 자세 표시명 (config/poses/*.json display_name) — 메시지 안에서도 치환된다
POSE_EN: dict[str, str] = {
    "앞으로 굽히기": "Forward Bend",
    "측면 굽히기": "Side Bend",
    "만세 (오버헤드 리치)": "Overhead Reach",
    "T-포즈 (팔 벌리기)": "T-Pose",
    "한 발 들기 밸런스": "One-Leg Balance",
}

# 정확 일치 사전 — 키는 화면에 그려지는 한국어 원문 그대로
EN: dict[str, str] = {
    # 게임 이름 (상단바·홈 카드와 동일 표기)
    "반응속도 테스트": "Reaction Test",
    "높이뛰기": "High Jump",
    "스트레칭 코스": "Stretching Course",
    "2인 대결": "2-Player Battle",
    "팔굽혀펴기": "Push-ups",
    # 공통 (session / games)
    "카메라 앞에 서 주세요": "Stand in front of the camera",
    "화면 안으로 들어와 주세요": "Step into the frame",
    "시작!": "GO!",
    "완료!": "Complete!",
    "따라해 보세요": "Follow along",
    "예시 준비 중": "Preparing example",
    "유연성 리포트": "Flexibility Report",
    "기록 없음": "no record",
    # 반응속도
    "손을 내리면 시작합니다": "Lower your hand to start",
    "신호가 뜨면 손을 번쩍!": "Raise your hand when the signal appears!",
    "너무 빨라요! 신호를 기다리세요": "Too soon! Wait for the signal",
    "지금! 손을 드세요!": "NOW! Raise your hand!",
    "손을 번쩍 드세요!": "Raise your hand!",
    "잠깐… 기다리세요": "Wait for it…",
    "시간 초과!": "Time out!",
    "손을 내려 주세요": "Lower your hand",
    "너무 빨라요! 다시 갑니다": "Too soon! Let's go again",
    "반응속도 결과": "Reaction Result",
    # 높이뛰기
    "가만히 서 주세요 — 기준 높이 측정 중": "Stand still — calibrating",
    "가만히 서 주세요 — 다시 측정합니다": "Stand still — recalibrating",
    "머리가 잘 보이게 서 주세요": "Make sure your head is visible",
    "준비 완료 — 힘껏 점프!": "Ready — jump as high as you can!",
    "점프!": "JUMP!",
    "높이뛰기 결과": "High Jump Result",
    "* 단일 카메라 근사치": "* single-camera estimate",
    # 팔굽혀펴기
    "팔굽혀펴기 자세를 잡아 주세요 (측면 권장)":
        "Get into push-up position (side view is best)",
    "허리를 곧게 펴 주세요": "Keep your back straight",
    "팔이 잘 보이게 자세를 잡아 주세요": "Make sure your arms are visible",
    "시작! 팔을 굽혔다 펴세요": "GO! Bend and extend your arms",
    "팔을 굽혔다 펴세요": "Bend and extend your arms",
    "측면(옆모습)이 잘 보이면 더 정확해요":
        "Side view gives the most accurate count",
    "팔굽혀펴기 결과": "Push-up Result",
    # 대결
    "두 명이 카메라 앞에 서 주세요": "Two players — stand in front of the camera",
    "한 명씩 화면 왼쪽/오른쪽에 서 주세요": "One player on each side of the screen",
    "무승부!": "Draw!",
    # 어트랙트 (라이브 미러)
    "지나가다 멈춰 보세요!": "Step right up!",
    "몸을 움직이면 화면이 반응해요": "Move — the screen reacts!",
    "AI 가 당신의 동작을 봅니다": "AI is watching your moves",
    "게임에 도전해 보세요!": "Come try the games!",
    "좋아요! 바로 그거예요": "Nice! That's it!",
    "손을 번쩍 들어 보세요!": "Try raising your hand!",
    "화면을 터치하면 게임을 고를 수 있어요  ▶": "Touch the screen to play  ▶",
}


def _tr(word: str) -> str:
    """캡처 그룹 번역 — 자세명/소문구는 사전·패턴을 거치고, 없으면 원문 유지."""
    return POSE_EN.get(word) or EN.get(word) or en(word) or word


# (정규식, 변환 함수) — 숫자/자세명이 들어간 동적 문구
_PATTERNS: list[tuple[re.Pattern, Callable[[re.Match], str]]] = [
    # session.py
    (re.compile(r"'(.+)' 준비"), lambda m: f"Get ready: {_tr(m[1])}"),
    (re.compile(r"'(.+)' — 자세를 잡아 주세요"),
     lambda m: f"Get into the pose: {_tr(m[1])}"),
    (re.compile(r"'(.+)' 유지 중… ([\d.]+)s"), lambda m: f"Hold it… {m[2]}s"),
    (re.compile(r"'(.+)' 자세를 맞춰 주세요"),
     lambda m: f"Match the pose: {_tr(m[1])}"),
    (re.compile(r"(\d+)초 뒤 다음 자세 — (.+)"),
     lambda m: f"Next pose in {m[1]}s — {_tr(m[2])}"),
    (re.compile(r"(\d+)초 뒤 결과 화면"), lambda m: f"Results in {m[1]}s"),
    # hud.next_grade_gap
    (re.compile(r"([SAB]) 등급까지 (\d+)점!"),
     lambda m: f"{m[2]} pts to grade {m[1]}!"),
    (re.compile(r"한 번 더\?  (.+)"), lambda m: f"One more try?  {_tr(m[1])}"),
    # reaction
    (re.compile(r"완료! 평균 (.+)"), lambda m: f"Done! Average {_tr(m[1])}"),
    (re.compile(r"평균 (.+) — 참여해 보세요!"),
     lambda m: f"Average {_tr(m[1])} — give it a try!"),
    (re.compile(r"평균 (\S+)   ·   최고 (\S+)"),
     lambda m: f"average {m[1]}   ·   best {m[2]}"),
    (re.compile(r"부정 출발 (\d+)회"), lambda m: f"{m[1]} false start(s)"),
    # jump
    (re.compile(r"(\d+)번째 시도 — 힘껏 점프!"),
     lambda m: f"Attempt {m[1]} — jump!"),
    (re.compile(r"최고 약 (\d+)cm!?"), lambda m: f"best ≈ {m[1]} cm"),
    (re.compile(r"완료! 최고 약 (\d+)cm"), lambda m: f"Done! Best ≈ {m[1]} cm"),
    (re.compile(r"기록: (.+)"), lambda m: f"attempts: {m[1]}"),
    # pushup
    (re.compile(r"완료! (\d+)개"), lambda m: f"Done! {m[1]} reps"),
    (re.compile(r"(\d+)개 — 계속!"), lambda m: f"{m[1]} reps — keep going!"),
    (re.compile(r"(\d+)개 \(바른 자세 (\d+)개\)"),
     lambda m: f"{m[1]} reps ({m[2]} with good form)"),
    (re.compile(r"자세 품질 (\d+)%"), lambda m: f"form quality {m[1]}%"),
    # versus
    (re.compile(r"Player (\d) 승리!"), lambda m: f"Player {m[1]} wins!"),
]


def en(kr: str) -> str | None:
    """한국어 문구의 영어 보조 표기. 등록되지 않았으면 None."""
    if not kr:
        return None
    hit = EN.get(kr)
    if hit is not None:
        return hit
    for rx, fn in _PATTERNS:
        m = rx.fullmatch(kr)
        if m:
            return fn(m)
    return None
