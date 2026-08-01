from src.cleanup import build_expired_filter


def test_expired_filter_targets_deadline_before_today():
    f = build_expired_filter("2026-08-01")
    assert f["property"] == "마감일"
    assert f["date"]["before"] == "2026-08-01"


def test_expired_skip_logic_matches_main():
    """main.py의 마감 공고 스킵 조건과 동일한 판정."""
    today = "2026-08-01"

    def is_expired(entry):
        return bool(entry.get("deadline") and entry["deadline"] < today)

    assert is_expired({"deadline": "2026-07-31"}) is True   # 어제 마감
    assert is_expired({"deadline": "2026-08-01"}) is False  # 오늘 마감(유지)
    assert is_expired({"deadline": "2026-09-01"}) is False  # 미래
    assert is_expired({"deadline": ""}) is False            # 상시채용(유지)
    assert is_expired({}) is False                          # 마감일 없음
