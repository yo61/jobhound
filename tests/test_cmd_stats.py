"""Tests for `jh stats`."""

import json


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_stats_prints_funnel(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["stats"])
    assert result.exit_code == 0, result.output
    assert "Funnel" in result.output
    assert "prospect" in result.output


def test_stats_json_flag(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["stats", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "funnel" in payload
    assert "sources" in payload


def test_stats_empty_db_succeeds(tmp_jh, invoke) -> None:
    result = invoke(["stats"])
    assert result.exit_code == 0, result.output


def _seed_active_plus_archived(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(["new", "--company", "Gone", "--role", "Staff", "--now", "2026-05-02T12:00:00Z"])
    invoke(["archive", "gone"])


def test_stats_default_excludes_archived(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # both seeded as prospect; default = active only -> exactly 1 prospect
    assert payload["funnel"]["prospect"] == 1


def test_stats_all_includes_archived(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--all", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["funnel"]["prospect"] == 2


def test_stats_archived_only(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--archived", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["funnel"]["prospect"] == 1


def test_stats_status_filter(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["stats", "--status", "applied", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["funnel"]["applied"] == 1
    assert payload["funnel"]["prospect"] == 0


def test_stats_all_and_archived_are_mutually_exclusive(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--all", "--archived"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_stats_unknown_status_errors(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--status", "made-up"])
    assert result.exit_code != 0
    assert "unknown status" in result.output


def test_stats_archived_with_status_filter(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    # "gone" was archived as prospect. Filter archived to prospect → 1 prospect.
    result = invoke(["stats", "--archived", "--status", "prospect", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["funnel"]["prospect"] == 1
    assert payload["funnel"]["applied"] == 0
