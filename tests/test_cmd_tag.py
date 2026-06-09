"""Tests for `jh tag add` and `jh tag remove`."""

from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_tag_add_adds_tag(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["tag", "add", "foo", "remote"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert "remote" in opp.tags


def test_tag_add_multiple(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["tag", "add", "foo", "remote"])
    invoke(["tag", "add", "foo", "uk"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert set(opp.tags) == {"remote", "uk"}


def test_tag_remove_removes_existing_tag(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["tag", "add", "foo", "remote"])
    invoke(["tag", "add", "foo", "uk"])
    result = invoke(["tag", "remove", "foo", "uk"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.tags == ("remote",)


def test_tag_remove_nonexistent_tag_is_noop(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["tag", "add", "foo", "remote"])
    result = invoke(["tag", "remove", "foo", "nonexistent"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.tags == ("remote",)


def test_tag_list_empty(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["tag", "list", "foo"])
    assert result.exit_code == 0


def test_tag_list_returns_tags(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["tag", "add", "foo", "remote"])
    invoke(["tag", "add", "foo", "priority"])
    result = invoke(["tag", "list", "foo"])
    assert result.exit_code == 0
    lines = set(result.output.splitlines())
    assert "remote" in lines
    assert "priority" in lines
