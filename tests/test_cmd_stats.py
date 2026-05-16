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
