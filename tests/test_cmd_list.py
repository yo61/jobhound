"""Tests for `jh list`."""


def test_list_one_line_per_opportunity(tmp_jh, invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(["new", "--company", "Bar", "--role", "IC", "--now", "2026-05-02T12:00:00Z"])
    result = invoke(["list"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output
    assert "prospect" in result.output
