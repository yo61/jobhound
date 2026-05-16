"""Tests for `jh remove tag`."""

from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_remove_tag_removes_existing_tag(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "tag", "foo", "remote"])
    invoke(["add", "tag", "foo", "uk"])
    result = invoke(["remove", "tag", "foo", "uk"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.tags == ("remote",)


def test_remove_tag_nonexistent_tag_is_noop(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "tag", "foo", "remote"])
    result = invoke(["remove", "tag", "foo", "nonexistent"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.tags == ("remote",)
