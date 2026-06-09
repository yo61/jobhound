"""Tests for `jh __complete` hidden subcommand and its dispatch."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _seed_slug(db_path: Path, slug: str) -> Path:
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "X"\nrole = "Y"\nslug = "{slug}"\n'
        'status = "applied"\npriority = "high"\nsource = "X"\n'
        "applied_on = 2026-05-01T12:00:00+00:00\n"
        "last_activity = 2026-05-01T12:00:00+00:00\n"
        "tags = []\n",
    )
    subprocess.run(["git", "-C", str(db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )
    return opp_dir


def test_complete_command_is_hidden_from_help(invoke) -> None:
    """`jh --help` must not list `__complete`."""
    result = invoke(["--help"])
    assert result.exit_code == 0
    assert "__complete" not in result.output


def test_complete_runs_and_exits_zero(invoke) -> None:
    """`jh __complete zsh jh ""` runs without error."""
    result = invoke(["__complete", "zsh", "jh", ""])
    assert result.exit_code == 0


def test_complete_top_level_lists_visible_commands(invoke) -> None:
    """`jh __complete zsh jh ""` lists top-level commands."""
    result = invoke(["__complete", "zsh", "jh", ""])
    out = set(result.output.split())
    assert "show" in out
    assert "list" in out
    assert "new" in out
    assert "file" in out
    assert "set" in out
    assert "clear" in out
    assert "contact" in out
    assert "note" in out
    assert "tag" in out
    assert "link" in out
    assert "__complete" not in out  # hidden


def test_complete_sub_app_lists_subcommands(invoke) -> None:
    """`jh __complete zsh jh file ""` lists `file` subcommands."""
    result = invoke(["__complete", "zsh", "jh", "file", ""])
    out = set(result.output.split())
    assert out == {"list", "read", "write", "append", "delete", "open", "import"}


def test_complete_show_returns_slugs(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh show ""` lists slugs from opportunities_dir."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    _seed_slug(tmp_jh.db_path, "2026-05-beta-eng")

    result = invoke(["__complete", "zsh", "jh", "show", ""])
    out = set(result.output.split())
    assert "2026-05-acme-em" in out
    assert "2026-05-beta-eng" in out


def test_complete_archive_returns_slugs(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh archive ""` lists slugs (archive takes a slug)."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    result = invoke(["__complete", "zsh", "jh", "archive", ""])
    assert "2026-05-acme-em" in result.output


def test_complete_show_returns_canonical_not_filtered(tmp_jh, invoke) -> None:
    """Slug completer returns ALL slugs regardless of partial prefix."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    _seed_slug(tmp_jh.db_path, "2026-05-beta-eng")

    result = invoke(["__complete", "zsh", "jh", "show", "ac"])
    out = set(result.output.split())
    assert "2026-05-acme-em" in out
    assert "2026-05-beta-eng" in out


def test_complete_file_open_returns_slugs(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh file open ""` lists slugs (slug at depth 2)."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    result = invoke(["__complete", "zsh", "jh", "file", "open", ""])
    assert "2026-05-acme-em" in result.output


@pytest.mark.parametrize("verb", ["add", "list", "show", "edit", "remove"])
def test_complete_note_verbs_return_slugs(tmp_jh, invoke, verb) -> None:
    """All five `jh note <verb>` shapes take a slug as first positional."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    result = invoke(["__complete", "zsh", "jh", "note", verb, ""])
    assert "2026-05-acme-em" in result.output


def test_complete_no_opps_dir_returns_empty(tmp_jh, invoke) -> None:
    """No opportunities_dir → no slug candidates; does not crash."""
    import shutil

    shutil.rmtree(tmp_jh.db_path / "opportunities")
    result = invoke(["__complete", "zsh", "jh", "show", ""])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_complete_file_open_filenames(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh file open <slug> ""` lists files in the opp."""
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    (opp_dir / "notes.md").write_text("hi\n")
    (opp_dir / "research.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "files", "--quiet"],
        check=True,
        capture_output=True,
    )

    result = invoke(["__complete", "zsh", "jh", "file", "open", "2026-05-acme-em", ""])
    lines = set(result.output.splitlines())
    assert "notes.md" in lines
    assert "research.md" in lines
    assert "meta.toml" not in lines  # meta.toml is protected; excluded by file_service.list_


def test_complete_filename_with_space_is_unquoted(tmp_jh, invoke) -> None:
    """Filenames with spaces are emitted as-is (one per line).

    The shell script does the quoting; the completer emits raw names.
    """
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    (opp_dir / "Job Description.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "f", "--quiet"],
        check=True,
        capture_output=True,
    )

    result = invoke(["__complete", "zsh", "jh", "file", "open", "2026-05-acme-em", ""])
    lines = set(result.output.splitlines())
    assert "Job Description.md" in lines  # exactly one line, with the space


def test_complete_filename_unresolvable_slug_empty(tmp_jh, invoke) -> None:
    """An unresolvable slug at position 0 → empty filename candidates."""
    result = invoke(["__complete", "zsh", "jh", "file", "open", "not-a-real-slug", ""])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_complete_file_import_position_path_emits_files_sentinel(invoke) -> None:
    """`jh file import <slug> <partial>` must signal local-filesystem completion.

    The second positional of `file import` is a local-disk source path, not
    a repo-side filename. The completer cannot enumerate the user's
    filesystem itself, so it emits a sentinel that the shell stub
    translates into native file completion.
    """
    from jobhound.commands._complete import FILES_SENTINEL

    result = invoke(["__complete", "bash", "jh", "file", "import", "any-slug", ""])
    assert result.exit_code == 0
    assert result.output.strip() == FILES_SENTINEL


def test_complete_file_import_does_not_emit_repo_filenames(tmp_jh, invoke) -> None:
    """`jh file import` position 1 must NOT emit repo-side filenames.

    Regression test for the original bug: `file import` was grouped with
    the repo-side file commands, so its local-path position completed
    against the slug's files instead.
    """
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    (opp_dir / "notes.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "f", "--quiet"],
        check=True,
        capture_output=True,
    )

    result = invoke(["__complete", "bash", "jh", "file", "import", "2026-05-acme-em", ""])
    lines = set(result.output.splitlines())
    assert "notes.md" not in lines


def test_complete_local_path_flag_values_emit_sentinel(invoke) -> None:
    """Local-filesystem `--flag <path>` positions emit the files sentinel.

    Covers every flag whose value is a local disk path: file read --out,
    file write --from, file append --from, log --body, completion
    install --dest.
    """
    from jobhound.commands._complete import FILES_SENTINEL

    cases = [
        ["__complete", "bash", "jh", "file", "read", "slug", "name", "--out", ""],
        ["__complete", "bash", "jh", "file", "write", "slug", "name", "--from", ""],
        ["__complete", "bash", "jh", "file", "append", "slug", "name", "--from", ""],
        ["__complete", "bash", "jh", "log", "slug", "--body", ""],
        ["__complete", "bash", "jh", "completion", "install", "--dest", ""],
    ]
    for args in cases:
        result = invoke(args)
        assert result.exit_code == 0, f"args={args!r}"
        assert result.output.strip() == FILES_SENTINEL, f"args={args!r}"


def test_complete_set_status_returns_status_enum(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh set status <slug> ""` lists Status values."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    result = invoke(["__complete", "zsh", "jh", "set", "status", "2026-05-acme-em", ""])
    out = set(result.output.split())
    expected = {
        "prospect",
        "applied",
        "screen",
        "interview",
        "offer",
        "accepted",
        "declined",
        "rejected",
        "withdrawn",
        "ghosted",
    }
    assert expected <= out


def test_complete_set_priority_to_flag_returns_priority_enum(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh set priority --to ""` lists Priority values."""
    result = invoke(["__complete", "zsh", "jh", "set", "priority", "--to", ""])
    out = set(result.output.split())
    assert out == {"high", "medium", "low"}


def test_complete_top_level_includes_unarchive(invoke) -> None:
    """`jh __complete zsh jh ""` lists `unarchive`."""
    result = invoke(["__complete", "zsh", "jh", ""])
    out = set(result.output.split())
    assert "unarchive" in out


def test_complete_unarchive_returns_archived_slugs_only(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh unarchive ""` lists slugs from archive_dir, not opportunities."""
    # Seed one active and one archived opportunity, both with deterministic slugs.
    _seed_slug(tmp_jh.db_path, "2026-05-active-em")
    archived = tmp_jh.db_path / "archive" / "2026-05-archived-em"
    archived.mkdir(parents=True)
    (archived / "correspondence").mkdir()
    (archived / "meta.toml").write_text(
        'company = "X"\nrole = "Y"\nslug = "2026-05-archived-em"\n'
        'status = "rejected"\npriority = "high"\nsource = "X"\n'
        "applied_on = 2026-05-01T12:00:00+00:00\n"
        "last_activity = 2026-05-01T12:00:00+00:00\n"
        "tags = []\n",
    )

    result = invoke(["__complete", "zsh", "jh", "unarchive", ""])
    out = set(result.output.split())
    assert "2026-05-archived-em" in out
    assert "2026-05-active-em" not in out


def test_static_tables_match_live_cyclopts_app() -> None:
    """Catch drift between static completion tables and the live App tree.

    If this test fails, you added or removed a command in cli.py (or a
    sub-App) without updating the static tables in _complete.py. Update
    _TOP_LEVEL_COMMANDS and/or _SUB_APP_NAMES to match.
    """
    from cyclopts import App

    from jobhound.cli import get_app
    from jobhound.commands._complete import _SUB_APP_NAMES, _TOP_LEVEL_COMMANDS

    top_app = get_app()

    def _visible_names(node: App) -> set[str]:
        names = set()
        for name, entry in getattr(node, "_commands", {}).items():
            if name.startswith("-"):
                continue
            if getattr(entry, "show", True) is False:
                continue
            names.add(name)
        return names

    live_top = _visible_names(top_app)
    assert live_top == _TOP_LEVEL_COMMANDS, (
        f"_TOP_LEVEL_COMMANDS drift: only in static={_TOP_LEVEL_COMMANDS - live_top}, "
        f"only in live={live_top - _TOP_LEVEL_COMMANDS}"
    )

    for sub_name, static_subverbs in _SUB_APP_NAMES.items():
        sub_app = top_app._commands[sub_name]
        assert isinstance(sub_app, App), f"{sub_name!r} is not a sub-App"
        live_subverbs = _visible_names(sub_app)
        assert live_subverbs == static_subverbs, (
            f"_SUB_APP_NAMES[{sub_name!r}] drift: "
            f"only in static={static_subverbs - live_subverbs}, "
            f"only in live={live_subverbs - static_subverbs}"
        )


def test_complete_contact_show_returns_contact_names(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh contact show <slug> ""` lists contact names."""
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    # Append contacts to meta.toml
    meta = opp_dir / "meta.toml"
    meta.write_text(
        meta.read_text()
        + '[[contacts]]\nname = "Charlotte Eyre"\nrole = "EM"\n'
        + '[[contacts]]\nname = "Jane Smith"\nrole = "Recruiter"\n'
    )
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "contacts", "--quiet"],
        check=True,
        capture_output=True,
    )
    result = invoke(["__complete", "zsh", "jh", "contact", "show", "2026-05-acme-em", ""])
    lines = set(result.output.splitlines())
    assert "Charlotte Eyre" in lines
    assert "Jane Smith" in lines


def test_complete_contact_edit_returns_contact_names(tmp_jh, invoke) -> None:
    """`jh contact edit` also gets name completion at position 1."""
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    meta = opp_dir / "meta.toml"
    meta.write_text(meta.read_text() + '[[contacts]]\nname = "Bob Smith"\n')
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "c", "--quiet"],
        check=True,
        capture_output=True,
    )
    result = invoke(["__complete", "zsh", "jh", "contact", "edit", "2026-05-acme-em", ""])
    assert "Bob Smith" in result.output.splitlines()


def test_complete_contact_show_dedupes_duplicate_names(tmp_jh, invoke) -> None:
    """When two contacts share a name, the completer emits it once."""
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    meta = opp_dir / "meta.toml"
    meta.write_text(
        meta.read_text()
        + '[[contacts]]\nname = "Jane Doe"\nrole = "Recruiter"\n'
        + '[[contacts]]\nname = "Jane Doe"\nrole = "HM"\n'
    )
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "c", "--quiet"],
        check=True,
        capture_output=True,
    )
    result = invoke(["__complete", "zsh", "jh", "contact", "show", "2026-05-acme-em", ""])
    lines = result.output.splitlines()
    assert lines.count("Jane Doe") == 1


def test_complete_contact_show_no_contacts_empty(tmp_jh, invoke) -> None:
    """Opp with no contacts → no candidates, no crash."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    result = invoke(["__complete", "zsh", "jh", "contact", "show", "2026-05-acme-em", ""])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_complete_contact_show_unresolvable_slug_empty(tmp_jh, invoke) -> None:
    """Unresolvable slug at position 0 → empty contact-name candidates."""
    result = invoke(["__complete", "zsh", "jh", "contact", "show", "not-a-real-slug", ""])
    assert result.exit_code == 0
    assert result.output.strip() == ""
