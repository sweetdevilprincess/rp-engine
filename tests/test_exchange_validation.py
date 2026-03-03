"""Tests for exchange content validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rp_engine.models.exchange import ExchangeSave


class TestExchangeValidation:
    def test_valid_exchange(self):
        e = ExchangeSave(
            user_message="Hello",
            assistant_response="Hi there! How are you?",
        )
        assert e.assistant_response == "Hi there! How are you?"

    def test_rejects_thinking_tags(self):
        with pytest.raises(ValidationError, match="thinking"):
            ExchangeSave(
                user_message="Test",
                assistant_response="<thinking>Internal thoughts</thinking>Visible text",
            )

    def test_rejects_thinking_tags_case_insensitive(self):
        with pytest.raises(ValidationError, match="thinking"):
            ExchangeSave(
                user_message="Test",
                assistant_response="<THINKING>stuff</THINKING>text",
            )

    def test_rejects_tool_calls(self):
        with pytest.raises(ValidationError, match="tool call"):
            ExchangeSave(
                user_message="Test",
                assistant_response='Some text {"tool_calls": [{"name": "test"}]} more text',
            )

    def test_rejects_system_reminders(self):
        with pytest.raises(ValidationError, match="system instructions"):
            ExchangeSave(
                user_message="Test",
                assistant_response="Text <system-reminder>secret stuff</system-reminder> more text",
            )

    def test_allows_normal_angle_brackets(self):
        e = ExchangeSave(
            user_message="Test",
            assistant_response="The value is 5 < 10 and > 3.",
        )
        assert "<" in e.assistant_response
