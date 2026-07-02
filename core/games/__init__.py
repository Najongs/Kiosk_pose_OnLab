"""미니게임 로직 (Qt 비의존).

각 게임은 core/session.py 패턴을 따른다: 상태 Enum + 렌더 계약 dataclass +
update(primary, now) -> State. 시간(now)과 난수(rng)는 외부 주입이라
헤드리스/가짜 시간으로 결정적 테스트가 가능하다.
"""
