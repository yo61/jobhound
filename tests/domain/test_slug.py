from jobhound.domain.slug import slugify


def test_slugify_lowercases_and_replaces_runs_of_non_alnum_with_dash():
    assert slugify("Charlotte Eyre Background") == "charlotte-eyre-background"


def test_slugify_strips_leading_trailing_dashes():
    assert slugify("  --hello world!!  ") == "hello-world"


def test_slugify_collapses_consecutive_separators():
    assert slugify("a   b___c") == "a-b-c"


def test_slugify_empty_when_only_separators():
    assert slugify("---") == ""


def test_slugify_keeps_digits():
    assert slugify("Q4 2026 plan") == "q4-2026-plan"
