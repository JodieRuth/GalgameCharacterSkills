from galgame_character_skills.utils import token_utils


def test_estimate_tokens_from_text_returns_zero_for_empty_input():
    assert token_utils.estimate_tokens_from_text("") == 0
    assert token_utils.estimate_tokens_from_text(None) == 0


def test_estimate_tokens_from_text_uses_tokenizer(monkeypatch):
    class FakeTokenizer:
        def encode(self, text):
            return [1, 2, 3]

    monkeypatch.setattr(token_utils, "_tokenizer", FakeTokenizer())
    assert token_utils.estimate_tokens_from_text("abc") == 3


def test_estimate_tokens_from_text_falls_back_when_tokenizer_errors(monkeypatch):
    class BrokenTokenizer:
        def encode(self, text):
            raise RuntimeError("broken")

    monkeypatch.setattr(token_utils, "_tokenizer", BrokenTokenizer())
    assert token_utils.estimate_tokens_from_text("abcd") == 2
    assert token_utils.estimate_tokens_from_text("a") == 1
