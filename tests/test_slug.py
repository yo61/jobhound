"""Tests for the slug resolver."""

from pathlib import Path

import pytest

from jobhound.slug import AmbiguousSlugError, SlugNotFoundError, resolve_slug


def _seed(root: Path, names: list[str]) -> Path:
    opp = root / "opportunities"
    opp.mkdir(parents=True)
    for n in names:
        (opp / n).mkdir()
    return opp


def test_exact_match(tmp_path: Path) -> None:
    opp = _seed(tmp_path, ["2026-05-foo-engineer", "2026-05-bar-engineer"])
    assert resolve_slug("2026-05-foo-engineer", opp) == opp / "2026-05-foo-engineer"


def test_unique_substring_match(tmp_path: Path) -> None:
    opp = _seed(tmp_path, ["2026-05-foo-engineer", "2026-05-bar-engineer"])
    assert resolve_slug("foo", opp) == opp / "2026-05-foo-engineer"


def test_ambiguous_match_raises(tmp_path: Path) -> None:
    opp = _seed(tmp_path, ["2026-05-foo-engineer", "2026-04-foo-em"])
    with pytest.raises(AmbiguousSlugError) as exc:
        resolve_slug("foo", opp)
    assert "2026-05-foo-engineer" in str(exc.value)
    assert "2026-04-foo-em" in str(exc.value)


def test_no_match_raises(tmp_path: Path) -> None:
    opp = _seed(tmp_path, ["2026-05-foo-engineer"])
    with pytest.raises(SlugNotFoundError):
        resolve_slug("nonesuch", opp)


def test_exact_match_wins_over_substring(tmp_path: Path) -> None:
    opp = _seed(tmp_path, ["foo", "foo-extended"])
    # "foo" is exact for "foo" and substring of "foo-extended"; exact must win.
    assert resolve_slug("foo", opp) == opp / "foo"
