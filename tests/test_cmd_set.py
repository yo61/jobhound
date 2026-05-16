"""Tests for `jh set` subgroup — priority, link, and the 10 deferred setters."""

from datetime import UTC, datetime

from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def _opp(tmp_jh):
    return read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")


def test_set_priority_sets_value(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "priority", "foo", "--to", "high"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).priority == Priority.HIGH


def test_set_priority_rejects_invalid_value(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "priority", "foo", "--to", "ultra"])
    assert result.exit_code != 0


def test_set_link_add_and_update(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "link", "foo", "--name", "posting", "--url", "https://e.com/1"])
    assert _opp(tmp_jh).links == {"posting": "https://e.com/1"}

    invoke(["set", "link", "foo", "--name", "posting", "--url", "https://e.com/2"])
    assert _opp(tmp_jh).links == {"posting": "https://e.com/2"}


def test_set_company(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "company", "foo", "Bar Corp"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).company == "Bar Corp"


def test_set_role(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "role", "foo", "Staff Engineer"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).role == "Staff Engineer"


def test_set_status(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "status", "foo", "applied"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).status == Status.APPLIED


def test_set_status_rejects_invalid_value(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "status", "foo", "unicorn"])
    assert result.exit_code != 0


def test_set_source(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "source", "foo", "LinkedIn"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).source == "LinkedIn"


def test_set_location(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "location", "foo", "London, UK"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).location == "London, UK"


def test_set_comp_range(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "comp-range", "foo", "80k-100k"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).comp_range == "80k-100k"


def test_set_first_contact(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "first-contact", "foo", "2026-04-01T09:00:00Z"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).first_contact == datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


def test_set_applied_on(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "applied-on", "foo", "2026-04-15T10:00:00Z"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).applied_on == datetime(2026, 4, 15, 10, 0, tzinfo=UTC)


def test_set_last_activity(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "last-activity", "foo", "2026-05-10T14:00:00Z"])
    assert result.exit_code == 0, result.output
    assert _opp(tmp_jh).last_activity == datetime(2026, 5, 10, 14, 0, tzinfo=UTC)


def test_set_next_action(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "next-action", "foo", "Send follow-up", "2026-05-20T09:00:00Z"])
    assert result.exit_code == 0, result.output
    opp = _opp(tmp_jh)
    assert opp.next_action == "Send follow-up"
    assert opp.next_action_due == datetime(2026, 5, 20, 9, 0, tzinfo=UTC)
