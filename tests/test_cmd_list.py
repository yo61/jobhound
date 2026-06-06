"""Tests for `jh list`."""


def _seed_active(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(["new", "--company", "Bar", "--role", "IC", "--now", "2026-05-02T12:00:00Z"])


def _seed_active_plus_archived(invoke) -> None:
    _seed_active(invoke)
    invoke(["new", "--company", "Gone", "--role", "Staff", "--now", "2026-05-03T12:00:00Z"])
    invoke(["archive", "gone"])


def test_list_default_shows_active_only(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["list"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output
    assert "2026-05-gone-staff" not in result.output


def test_list_one_line_per_opportunity(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    result = invoke(["list"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output
    assert "prospect" in result.output


def test_list_all_includes_archived_with_asterisk(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["list", "--all"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-gone-staff" in result.output
    # archived row ends with a trailing asterisk
    for line in result.output.splitlines():
        if "2026-05-gone-staff" in line:
            assert line.rstrip().endswith("*")
        elif line.strip() and not line.startswith(" "):
            assert not line.rstrip().endswith("*")


def test_list_archived_shows_only_archived(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["list", "--archived"])
    assert result.exit_code == 0, result.output
    assert "2026-05-gone-staff" in result.output
    assert "2026-05-foo-em" not in result.output
    assert "2026-05-bar-ic" not in result.output


def test_list_all_and_archived_are_mutually_exclusive(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    result = invoke(["list", "--all", "--archived"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_list_status_filter_single(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["list", "--status", "applied"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" not in result.output


def test_list_status_filter_repeated(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["list", "--status", "applied", "--status", "prospect"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output


def test_list_status_filter_comma_separated(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["list", "--status", "applied,prospect"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output


def test_list_status_filter_unknown_value_errors(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    result = invoke(["list", "--status", "made-up"])
    assert result.exit_code != 0
    assert "unknown status" in result.output


def test_list_all_status_filter_composes(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    # "gone" was archived as prospect. Filter by prospect across both sets.
    result = invoke(["list", "--all", "--status", "prospect"])
    assert result.exit_code == 0, result.output
    assert "2026-05-gone-staff" in result.output
    assert "2026-05-foo-em" in result.output
