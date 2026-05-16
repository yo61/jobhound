"""Tests for `jh clear` subgroup — 7 nullable-field clearers."""

from __future__ import annotations

from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def _opp(tmp_jh):
    return read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")


def test_clear_source(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "source", "foo", "LinkedIn"])
    result = invoke(["clear", "source", "foo"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).source is None


def test_clear_location(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "location", "foo", "London"])
    result = invoke(["clear", "location", "foo"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).location is None


def test_clear_comp_range(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "comp-range", "foo", "80k-100k"])
    result = invoke(["clear", "comp-range", "foo"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).comp_range is None


def test_clear_first_contact(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "first-contact", "foo", "2026-04-01T09:00:00Z"])
    result = invoke(["clear", "first-contact", "foo"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).first_contact is None


def test_clear_applied_on(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "applied-on", "foo", "2026-04-15T10:00:00Z"])
    result = invoke(["clear", "applied-on", "foo"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).applied_on is None


def test_clear_last_activity(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "last-activity", "foo", "2026-05-10T14:00:00Z"])
    result = invoke(["clear", "last-activity", "foo"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).last_activity is None


def test_clear_next_action_clears_both_fields(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "next-action", "foo", "Send follow-up", "2026-05-20T09:00:00Z"])
    result = invoke(["clear", "next-action", "foo"])
    assert result.exit_code == 0, result.output
    opp = _opp(tmp_jh)
    assert opp.next_action is None
    assert opp.next_action_due is None
