"""Tiny text helpers used by the video demonstration."""


def word_count(text: str) -> int:
    """Return the number of whitespace-separated words in text."""
    return len(text.split(" "))


def unique_words(text: str) -> set[str]:
    """Return lowercase whitespace-separated words."""
    return {word.lower() for word in text.split()}
