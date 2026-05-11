"""Tests for jh link and jh contact."""

from jobhound.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-01"])


def test_link_add_and_update(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["link", "foo", "--name", "posting", "--url", "https://e.com/1"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.links == {"posting": "https://e.com/1"}

    invoke(["link", "foo", "--name", "posting", "--url", "https://e.com/2"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.links == {"posting": "https://e.com/2"}


def test_contact_appends(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(
        [
            "contact",
            "foo",
            "--name",
            "Jane Doe",
            "--role-title",
            "Recruiter",
            "--channel",
            "email",
        ]
    )
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.contacts == ({"name": "Jane Doe", "role": "Recruiter", "channel": "email"},)
