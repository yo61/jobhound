"""Tests for `jh edit`. Editor is monkeypatched to a scripted operation."""

import pytest

from jobhound.meta_io import read_meta
from jobhound.priority import Priority


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-01"])


def _set_editor_to_sed(monkeypatch: pytest.MonkeyPatch, sed_expr: str) -> None:
    """Set $EDITOR to a script that runs `sed -i '' <expr> <file>` (BSD sed)."""
    monkeypatch.setenv("EDITOR", f"sed -i '' -e {sed_expr!r}")


def test_edit_no_changes_is_noop(tmp_jh, invoke, monkeypatch) -> None:
    _seed(invoke)
    monkeypatch.setenv("EDITOR", "true")  # exit cleanly without writing
    result = invoke(["edit", "foo"])
    assert result.exit_code == 0, result.output
    assert "no changes" in result.output.lower()


def test_edit_updates_priority(tmp_jh, invoke, monkeypatch) -> None:
    _seed(invoke)
    _set_editor_to_sed(monkeypatch, 's/priority = "medium"/priority = "high"/')
    result = invoke(["edit", "foo"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.priority == Priority.HIGH


def test_edit_rename_on_slug_change(tmp_jh, invoke, monkeypatch) -> None:
    _seed(invoke)
    _set_editor_to_sed(
        monkeypatch,
        's/slug = "2026-05-foo-em"/slug = "2026-05-foo-engineering-manager"/',
    )
    result = invoke(["edit", "foo"])
    assert result.exit_code == 0, result.output
    new = tmp_jh.db_path / "opportunities" / "2026-05-foo-engineering-manager"
    assert new.is_dir()
    assert not (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").exists()
