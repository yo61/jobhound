"""Tests for `jh set priority` and `jh set link`."""

from jobhound.domain.priority import Priority
from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_set_priority_sets_value(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "priority", "foo", "--to", "high"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.priority == Priority.HIGH


def test_set_priority_rejects_invalid_value(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["set", "priority", "foo", "--to", "ultra"])
    assert result.exit_code != 0


def test_set_link_add_and_update(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["set", "link", "foo", "--name", "posting", "--url", "https://e.com/1"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.links == {"posting": "https://e.com/1"}

    invoke(["set", "link", "foo", "--name", "posting", "--url", "https://e.com/2"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.links == {"posting": "https://e.com/2"}
