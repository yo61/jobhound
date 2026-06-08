"""End-to-end tests for `jh note` CLI verbs."""

from __future__ import annotations

from pathlib import Path

NOW_ISO = "2026-05-11T12:00:00Z"


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", NOW_ISO])


def _opp_dir(tmp_jh) -> Path:
    return tmp_jh.db_path / "opportunities" / "2026-05-foo-em"


# ── add ──────────────────────────────────────────────────────────────────


def test_add_positional_body(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["note", "add", "foo", "first contact made", "--now", NOW_ISO])
    assert result.exit_code == 0, result.output
    assert "noted: " in result.output
    assert "#1" in result.output
    assert (_opp_dir(tmp_jh) / "notes" / "1.md").exists()


def test_add_with_title_slugifies_filename(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(
        ["note", "add", "foo", "background", "--title", "Charlotte Eyre Prep", "--now", NOW_ISO]
    )
    assert result.exit_code == 0, result.output
    assert (_opp_dir(tmp_jh) / "notes" / "1-charlotte-eyre-prep.md").exists()


def test_add_from_path(tmp_jh, invoke, tmp_path) -> None:
    _seed(invoke)
    src = tmp_path / "draft.md"
    src.write_text("from a file")
    result = invoke(["note", "add", "foo", "--from", str(src), "--now", NOW_ISO])
    assert result.exit_code == 0, result.output
    contents = (_opp_dir(tmp_jh) / "notes" / "1.md").read_text()
    assert "from a file" in contents


def test_add_rejects_both_body_and_from(tmp_jh, invoke, tmp_path) -> None:
    _seed(invoke)
    src = tmp_path / "x.md"
    src.write_text("x")
    result = invoke(["note", "add", "foo", "body", "--from", str(src), "--now", NOW_ISO])
    assert result.exit_code != 0


def test_add_rejects_neither_body_nor_from(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["note", "add", "foo", "--now", NOW_ISO])
    assert result.exit_code != 0


def test_add_rejects_empty_body(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["note", "add", "foo", "   ", "--now", NOW_ISO])
    assert result.exit_code != 0


# ── list ─────────────────────────────────────────────────────────────────


def test_list_empty(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["note", "list", "foo"])
    assert result.exit_code == 0
    # The "no notes" message goes to stderr in our impl; output may not contain it via
    # cyclopts' capture. Just verify exit code.


def test_list_shows_seqs_and_titles(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "a", "--now", NOW_ISO])
    invoke(["note", "add", "foo", "b", "--title", "kickoff", "--now", NOW_ISO])
    invoke(["note", "add", "foo", "c", "--now", NOW_ISO])
    result = invoke(["note", "list", "foo"])
    assert result.exit_code == 0
    assert "1" in result.output
    assert "2" in result.output
    assert "3" in result.output
    assert "kickoff" in result.output


def test_list_preserves_gaps_after_remove(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "a", "--now", NOW_ISO])
    invoke(["note", "add", "foo", "b", "--now", NOW_ISO])
    invoke(["note", "add", "foo", "c", "--now", NOW_ISO])
    invoke(["note", "remove", "foo", "2", "--now", NOW_ISO])
    result = invoke(["note", "list", "foo"])
    assert result.exit_code == 0
    # Ensure 2 is not in any data row — split header from rows
    rows = "\n".join(result.output.splitlines()[1:])
    # Look for "  2 " or "  2|"  format — better: find the seq column entries
    # by checking each line starts with "  N " for some N.
    seq_lines = [ln for ln in rows.splitlines() if ln.strip() and ln.split()[0].isdigit()]
    seqs = [int(ln.split()[0]) for ln in seq_lines]
    assert seqs == [1, 3]


# ── show ─────────────────────────────────────────────────────────────────


def test_show_body_only(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "hello world", "--now", NOW_ISO])
    result = invoke(["note", "show", "foo", "1"])
    assert result.exit_code == 0
    assert result.output.strip() == "hello world"


def test_show_with_frontmatter(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "hello", "--now", NOW_ISO])
    result = invoke(["note", "show", "foo", "1", "--with-frontmatter"])
    assert result.exit_code == 0
    assert "+++" in result.output
    assert "created = 2026-05-11T12:00:00Z" in result.output


def test_show_missing_seq(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["note", "show", "foo", "5"])
    assert result.exit_code != 0


# ── edit ─────────────────────────────────────────────────────────────────


def test_edit_from_path(tmp_jh, invoke, tmp_path) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "v1", "--now", NOW_ISO])
    new_body = tmp_path / "new.md"
    new_body.write_text("v2")
    result = invoke(["note", "edit", "foo", "1", "--from", str(new_body), "--now", NOW_ISO])
    assert result.exit_code == 0, result.output
    show = invoke(["note", "show", "foo", "1"])
    assert show.output.strip() == "v2"


def test_edit_preserves_title(tmp_jh, invoke, tmp_path) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "v1", "--title", "kickoff", "--now", NOW_ISO])
    new_body = tmp_path / "new.md"
    new_body.write_text("v2")
    invoke(["note", "edit", "foo", "1", "--from", str(new_body), "--now", NOW_ISO])
    # File name should still be 1-kickoff.md
    assert (_opp_dir(tmp_jh) / "notes" / "1-kickoff.md").exists()


def test_edit_no_editor_and_no_from_fails(tmp_jh, invoke, monkeypatch) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "v1", "--now", NOW_ISO])
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    # Force a non-existent editor by overriding PATH so `vi` isn't findable
    monkeypatch.setenv("EDITOR", "/nonexistent/no-such-editor-xyzzy")
    result = invoke(["note", "edit", "foo", "1", "--now", NOW_ISO])
    assert result.exit_code != 0


def test_edit_missing_seq(tmp_jh, invoke, tmp_path) -> None:
    _seed(invoke)
    src = tmp_path / "x.md"
    src.write_text("x")
    result = invoke(["note", "edit", "foo", "99", "--from", str(src), "--now", NOW_ISO])
    assert result.exit_code != 0


# ── remove ───────────────────────────────────────────────────────────────


def test_remove_deletes_file(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "x", "--now", NOW_ISO])
    result = invoke(["note", "remove", "foo", "1", "--now", NOW_ISO])
    assert result.exit_code == 0
    assert not (_opp_dir(tmp_jh) / "notes" / "1.md").exists()


def test_remove_missing_seq(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["note", "remove", "foo", "5", "--now", NOW_ISO])
    assert result.exit_code != 0


# ── round-trip ───────────────────────────────────────────────────────────


def test_add_remove_add_creates_gap(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "a", "--now", NOW_ISO])
    invoke(["note", "remove", "foo", "1", "--now", NOW_ISO])
    invoke(["note", "add", "foo", "b", "--now", NOW_ISO])
    # The second add should NOT reuse seq 1; it should be seq 2.
    assert (_opp_dir(tmp_jh) / "notes" / "2.md").exists()
    assert not (_opp_dir(tmp_jh) / "notes" / "1.md").exists()
