from backend.integrations.chesstempo.fetch_attempts_csv import summarize_csv


def test_summarize_csv_aggregates_per_day_with_adjusted_minutes() -> None:
    csv_text = "\n".join(
        [
            '"Date","Used <ct-icon name=""timer""></ct-icon>"',
            '"2026-02-20T10:00:00Z","30"',
            '"2026-02-20T11:00:00Z","45"',
            '"2026-02-19T21:00:00Z","30"',
        ]
    )
    summary = summarize_csv(csv_text.encode("utf-8"), "Europe/Amsterdam")

    assert summary["rows_total"] == 3
    assert summary["rows_used"] == 3
    assert summary["rows_skipped"] == 0
    assert summary["daily"] == [
        {"date": "2026-02-20", "exercises": 2, "adjusted_minutes": 2},
        {"date": "2026-02-19", "exercises": 1, "adjusted_minutes": 1},
    ]


def test_summarize_csv_counts_skipped_rows() -> None:
    csv_text = "\n".join(
        [
            '"Date","Used <ct-icon name=""timer""></ct-icon>"',
            '"2026-02-20T10:00:00Z","30"',
            '"bad-date","30"',
            '"2026-02-20T11:00:00Z","not-a-number"',
        ]
    )
    summary = summarize_csv(csv_text.encode("utf-8"), "Europe/Amsterdam")

    assert summary["rows_total"] == 3
    assert summary["rows_used"] == 1
    assert summary["rows_skipped"] == 2
    assert summary["daily"] == [
        {"date": "2026-02-20", "exercises": 1, "adjusted_minutes": 1},
    ]


def test_summarize_csv_falls_back_to_used_column_name() -> None:
    csv_text = "\n".join(
        [
            '"Date","Used Seconds"',
            '"2026-02-20T10:00:00Z","30"',
        ]
    )
    summary = summarize_csv(csv_text.encode("utf-8"), "Europe/Amsterdam")

    assert summary["daily"] == [
        {"date": "2026-02-20", "exercises": 1, "adjusted_minutes": 1},
    ]


def test_summarize_csv_groups_rows_by_timezone_day() -> None:
    csv_text = "\n".join(
        [
            '"Date","Used <ct-icon name=""timer""></ct-icon>"',
            '"2026-02-20T23:30:00+00:00","30"',
        ]
    )
    summary = summarize_csv(csv_text.encode("utf-8"), "Europe/Amsterdam")

    assert summary["daily"] == [
        {"date": "2026-02-21", "exercises": 1, "adjusted_minutes": 1},
    ]
