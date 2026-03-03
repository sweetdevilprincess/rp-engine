"""Tests for normalization utilities."""

from rp_engine.utils.normalization import (
    file_to_key,
    id_to_key,
    normalize_key,
    strip_parenthetical,
)


class TestNormalizeKey:
    def test_basic(self):
        assert normalize_key("Dante Moretti") == "dante moretti"

    def test_strips_whitespace(self):
        assert normalize_key("  Dante  ") == "dante"

    def test_empty_string(self):
        assert normalize_key("") == ""

    def test_already_normalized(self):
        assert normalize_key("dante") == "dante"


class TestFileToKey:
    def test_strips_md(self):
        assert file_to_key("Dante Moretti.md") == "dante moretti"

    def test_no_extension(self):
        assert file_to_key("Dante Moretti") == "dante moretti"

    def test_uppercase_md(self):
        assert file_to_key("Test.MD") == "test"

    def test_empty(self):
        assert file_to_key("") == ""


class TestIdToKey:
    def test_underscores_to_spaces(self):
        assert id_to_key("memory_lilith_wakes_with_dante") == "memory lilith wakes with dante"

    def test_no_underscores(self):
        assert id_to_key("dante") == "dante"

    def test_empty(self):
        assert id_to_key("") == ""


class TestStripParenthetical:
    def test_strips_parenthetical(self):
        assert strip_parenthetical("Dante Moretti (resident)") == "Dante Moretti"

    def test_no_parenthetical(self):
        assert strip_parenthetical("Dante Moretti") == "Dante Moretti"

    def test_multiple_parens_strips_last(self):
        assert strip_parenthetical("Name (a) (b)") == "Name (a)"

    def test_empty(self):
        assert strip_parenthetical("") == ""
