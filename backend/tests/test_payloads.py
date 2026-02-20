from backend.app.chessdojo import (
    build_progress_payload,
    merge_requirements,
    resolve_previous_count,
)


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


def test_build_progress_payload_supports_time_only_increment_zero() -> None:
    user_payload = {
        "dojoCohort": "1100-1200",
        "progress": {"custom-1": {"counts": {"ALL_COHORTS": 0}}},
    }
    requirement = {"id": "custom-1", "startCount": 0}
    result = build_progress_payload(
        user_payload=user_payload,
        requirement=requirement,
        count_increment=0,
        minutes_spent=15,
    )
    assert result["previousCount"] == 0
    assert result["newCount"] == 0
    assert result["incrementalMinutesSpent"] == 15


def test_merge_requirements_includes_custom_tasks_from_access_payload() -> None:
    requirements_payload = [
        {
            "id": "builtin-1",
            "name": "Built-in",
            "category": "Study",
            "counts": {"1100-1200": 10},
        }
    ]
    custom_access_payload = {
        "customRequirements": [
            {
                "id": "custom-1",
                "name": "Custom Timer Task",
                "category": "Custom",
                "isCustomRequirement": True,
                "timeOnly": True,
            }
        ]
    }

    merged = merge_requirements(requirements_payload, custom_access_payload)
    merged_ids = {item["id"] for item in merged}
    assert merged_ids == {"builtin-1", "custom-1"}
    custom = next(item for item in merged if item["id"] == "custom-1")
    assert custom["isCustomRequirement"] is True
    assert custom["timeOnly"] is True
