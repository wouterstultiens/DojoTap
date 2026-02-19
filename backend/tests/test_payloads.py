from backend.app.chessdojo import build_progress_payload, resolve_previous_count


def test_resolve_previous_count_prefers_cohort() -> None:
    progress = {"counts": {"1100-1200": 9, "ALL_COHORTS": 3}}
    assert resolve_previous_count(progress, "1100-1200", 0) == 9


def test_resolve_previous_count_falls_back_all_cohorts() -> None:
    progress = {"counts": {"ALL_COHORTS": 7}}
    assert resolve_previous_count(progress, "1100-1200", 0) == 7


def test_resolve_previous_count_falls_back_start_count() -> None:
    assert resolve_previous_count({}, "1100-1200", 12) == 12


def test_build_progress_payload_math() -> None:
    user_payload = {
        "dojoCohort": "1100-1200",
        "progress": {"abc": {"counts": {"ALL_COHORTS": 438}}},
    }
    requirement = {"id": "abc", "startCount": 306}
    result = build_progress_payload(
        user_payload=user_payload,
        requirement=requirement,
        count_increment=2,
        minutes_spent=40,
    )
    assert result["cohort"] == "1100-1200"
    assert result["previousCount"] == 438
    assert result["newCount"] == 440
    assert result["incrementalMinutesSpent"] == 40
    assert result["date"].endswith("Z")

