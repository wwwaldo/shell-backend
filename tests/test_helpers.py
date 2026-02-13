"""Unit tests for helper functions."""

from main import _title_from_first_message


class TestTitleFromFirstMessage:
    """Tests for conversation title derivation."""

    def test_short_message(self):
        assert _title_from_first_message("Hello") == "Hello"

    def test_first_sentence_with_period(self):
        assert _title_from_first_message("What is Python? It's a language.") == "What is Python?"

    def test_truncates_long_message(self):
        long = "A" * 100
        assert _title_from_first_message(long) == "A" * 60 + "..."

    def test_empty_returns_default(self):
        assert _title_from_first_message("") == "New conversation"
        assert _title_from_first_message("   ") == "New conversation"
