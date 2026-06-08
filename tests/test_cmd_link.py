"""Tests for `jh link set` and `jh link remove`."""

from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def _opp(tmp_jh):
    return read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")


def test_link_set_add_and_update(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["link", "set", "foo", "--name", "posting", "--url", "https://e.com/1"])
    assert _opp(tmp_jh).links == {"posting": "https://e.com/1"}

    invoke(["link", "set", "foo", "--name", "posting", "--url", "https://e.com/2"])
    assert _opp(tmp_jh).links == {"posting": "https://e.com/2"}


def test_link_remove_removes_named_link(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["link", "set", "foo", "--name", "posting", "--url", "https://e.com/1"])
    invoke(["link", "set", "foo", "--name", "company", "--url", "https://foo.com"])
    result = invoke(["link", "remove", "foo", "--name", "posting"])
    assert result.exit_code == 0, result.output
    opp = _opp(tmp_jh)
    assert "posting" not in opp.links
    assert opp.links["company"] == "https://foo.com"


def test_link_remove_preserves_other_links(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["link", "set", "foo", "--name", "a", "--url", "https://a.com"])
    invoke(["link", "set", "foo", "--name", "b", "--url", "https://b.com"])
    invoke(["link", "remove", "foo", "--name", "a"])
    assert _opp(tmp_jh).links == {"b": "https://b.com"}


def test_link_remove_not_found_raises(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["link", "set", "foo", "--name", "posting", "--url", "https://e.com/1"])
    result = invoke(["link", "remove", "foo", "--name", "nonexistent"])
    assert result.exit_code != 0
