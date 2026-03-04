"""Tests for rp_engine.utils.json_helpers."""

from rp_engine.utils.json_helpers import safe_parse_json, safe_parse_json_array, safe_parse_json_list


class TestSafeParseJson:
    def test_none_returns_empty_dict(self):
        assert safe_parse_json(None) == {}

    def test_dict_passthrough(self):
        d = {"key": "value"}
        assert safe_parse_json(d) is d

    def test_valid_json_string(self):
        assert safe_parse_json('{"a": 1}') == {"a": 1}

    def test_invalid_json_returns_empty(self):
        assert safe_parse_json("not json") == {}

    def test_json_array_returns_default(self):
        assert safe_parse_json("[1, 2]") == {}

    def test_custom_default(self):
        assert safe_parse_json(None, default={"x": 1}) == {"x": 1}

    def test_empty_string(self):
        assert safe_parse_json("") == {}


class TestSafeParseJsonList:
    def test_none_returns_empty(self):
        assert safe_parse_json_list(None) == []

    def test_list_passthrough_stringifies(self):
        assert safe_parse_json_list(["a", "b"]) == ["a", "b"]

    def test_list_of_ints_stringified(self):
        assert safe_parse_json_list([1, 2]) == ["1", "2"]

    def test_valid_json_string(self):
        assert safe_parse_json_list('["x", "y"]') == ["x", "y"]

    def test_invalid_json_returns_empty(self):
        assert safe_parse_json_list("bad") == []

    def test_json_dict_returns_empty(self):
        assert safe_parse_json_list('{"a": 1}') == []

    def test_empty_list(self):
        assert safe_parse_json_list([]) == []


class TestSafeParseJsonArray:
    def test_none_returns_empty(self):
        assert safe_parse_json_array(None) == []

    def test_list_passthrough_preserves_types(self):
        data = [{"type": "expr", "fn": "any"}, "plain"]
        assert safe_parse_json_array(data) is data

    def test_valid_json_with_dicts(self):
        result = safe_parse_json_array('[{"a": 1}, {"b": 2}]')
        assert result == [{"a": 1}, {"b": 2}]

    def test_invalid_json_returns_empty(self):
        assert safe_parse_json_array("bad") == []

    def test_json_dict_returns_empty(self):
        assert safe_parse_json_array('{"a": 1}') == []
