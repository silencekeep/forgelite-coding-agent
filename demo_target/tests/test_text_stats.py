import unittest

from text_stats import unique_words, word_count


class TextStatsTests(unittest.TestCase):
    def test_word_count_handles_repeated_whitespace(self) -> None:
        self.assertEqual(word_count("one   two\n three\t four"), 4)

    def test_word_count_of_blank_text_is_zero(self) -> None:
        self.assertEqual(word_count("   \t\n"), 0)

    def test_unique_words_are_lowercase(self) -> None:
        self.assertEqual(unique_words("Red red BLUE"), {"red", "blue"})


if __name__ == "__main__":
    unittest.main()
