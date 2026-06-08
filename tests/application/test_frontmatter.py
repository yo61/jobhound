from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from jobhound.application.frontmatter import (
    Document,
    Frontmatter,
    FrontmatterError,
    parse,
    parse_or_synthesize,
    serialize,
)


def _fm(**kwargs):
    base = {"created": datetime(2026, 6, 8, 14, 23, 5, tzinfo=UTC)}
    return Frontmatter(**(base | kwargs))


def test_serialize_minimal():
    doc = Document(_fm(), body="Hello world.")
    out = serialize(doc)
    assert b"+++\n" in out
    assert b"created = 2026-06-08T14:23:05Z\n" in out
    assert b"title" not in out
    assert out.endswith(b"Hello world.\n")


def test_serialize_with_title():
    doc = Document(_fm(title="Charlotte prep"), body="Body.")
    out = serialize(doc)
    assert b'title = "Charlotte prep"\n' in out


def test_parse_roundtrip_minimal():
    doc = Document(_fm(), body="Hello.")
    assert parse(serialize(doc)) == doc


def test_parse_roundtrip_with_title():
    doc = Document(_fm(title="kickoff"), body="One\nTwo\nThree")
    assert parse(serialize(doc)) == doc


def test_parse_rejects_empty():
    with pytest.raises(FrontmatterError, match="empty"):
        parse(b"")


def test_parse_rejects_unclosed_frontmatter():
    with pytest.raises(FrontmatterError, match="unclosed"):
        parse(b"+++\ncreated = 2026-06-08T14:23:05Z\n\nbody but no closing")


def test_parse_rejects_missing_created():
    with pytest.raises(FrontmatterError, match="created"):
        parse(b'+++\ntitle = "x"\n+++\n\nbody')


def test_parse_rejects_naive_created():
    with pytest.raises(FrontmatterError, match="tz-aware"):
        parse(b"+++\ncreated = 2026-06-08T14:23:05\n+++\n\nbody")


def test_parse_rejects_invalid_toml():
    with pytest.raises(FrontmatterError):
        parse(b"+++\nthis is = = not toml\n+++\n\nbody")


def test_parse_or_synthesize_on_bare_markdown():
    fallback = datetime(2025, 1, 1, tzinfo=UTC)
    doc = parse_or_synthesize(b"Just markdown.\n", fallback)
    assert doc.frontmatter.created == fallback
    assert doc.frontmatter.title is None
    assert doc.body == "Just markdown."


def test_extras_passthrough():
    raw = b'+++\ncreated = 2026-06-08T14:23:05Z\nchannel = "email"\ndirection = "to"\n+++\n\nbody'
    doc = parse(raw)
    assert doc.frontmatter.extras == {"channel": "email", "direction": "to"}


@given(
    second=st.integers(min_value=0, max_value=59),
    minute=st.integers(min_value=0, max_value=59),
    hour=st.integers(min_value=0, max_value=23),
    title=st.one_of(
        st.none(),
        st.text(
            alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters='"\\'),
            min_size=1,
            max_size=40,
        ),
    ),
    body=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=400,
    ),
)
def test_property_roundtrip(second, minute, hour, title, body):
    created = datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC)
    doc = Document(Frontmatter(created=created, title=title), body=body.strip() or "x")
    assert parse(serialize(doc)) == doc
