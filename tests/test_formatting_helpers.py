"""Tests for formatting_helpers.py."""

import pytest
from formatting_helpers import (
    decimal_to_mixed_fraction,
    format_ingredients_for_display,
    format_instructions_for_display,
    normalize_ingredient_input,
)


# ---------------------------------------------------------------------------
# decimal_to_mixed_fraction
# ---------------------------------------------------------------------------

class TestDecimalToMixedFraction:
    def test_whole_number(self):
        assert decimal_to_mixed_fraction("2.0") == "2"

    def test_half(self):
        assert decimal_to_mixed_fraction("0.5") == "1/2"

    def test_one_and_a_half(self):
        assert decimal_to_mixed_fraction("1.5") == "1 1/2"

    def test_one_and_a_quarter(self):
        assert decimal_to_mixed_fraction("1.25") == "1 1/4"

    def test_three_quarters(self):
        assert decimal_to_mixed_fraction("0.75") == "3/4"

    def test_negative_half(self):
        assert decimal_to_mixed_fraction("-0.5") == "-1/2"

    def test_non_numeric_passthrough(self):
        assert decimal_to_mixed_fraction("abc") == "abc"

    def test_integer_string(self):
        assert decimal_to_mixed_fraction("3") == "3"


# ---------------------------------------------------------------------------
# format_ingredients_for_display
# ---------------------------------------------------------------------------

class TestFormatIngredientsForDisplay:
    def test_converts_decimal_in_ingredient(self):
        result = format_ingredients_for_display("0.5 cup flour")
        assert "1/2" in result

    def test_multi_line(self):
        text = "0.5 cup flour\n1.5 tsp salt"
        result = format_ingredients_for_display(text)
        assert "1/2" in result
        assert "1 1/2" in result

    def test_no_decimals_unchanged(self):
        text = "1 cup flour\n2 eggs"
        assert format_ingredients_for_display(text) == text

    def test_non_string_returns_empty(self):
        assert format_ingredients_for_display(None) == ""  # type: ignore[arg-type]
        assert format_ingredients_for_display(42) == ""  # type: ignore[arg-type]

    def test_empty_string(self):
        assert format_ingredients_for_display("") == ""


# ---------------------------------------------------------------------------
# normalize_ingredient_input
# ---------------------------------------------------------------------------

class TestNormalizeIngredientInput:
    def test_unicode_half(self):
        result = normalize_ingredient_input("½ cup sugar")
        assert "1/2" in result

    def test_unicode_quarter(self):
        result = normalize_ingredient_input("¼ tsp salt")
        assert "1/4" in result

    def test_unicode_three_quarters(self):
        result = normalize_ingredient_input("¾ cup milk")
        assert "3/4" in result

    def test_digit_adjacent_unicode_fraction(self):
        result = normalize_ingredient_input("1½ cups flour")
        assert "1 1/2" in result

    def test_unicode_fraction_slash(self):
        result = normalize_ingredient_input("1⁄2 cup water")
        assert "1/2" in result

    def test_plain_ascii_unchanged(self):
        result = normalize_ingredient_input("2 cups milk")
        assert "2 cups milk" in result

    def test_non_string_returns_empty(self):
        assert normalize_ingredient_input(None) == ""  # type: ignore[arg-type]

    def test_multiline_preserved(self):
        text = "½ cup sugar\n¼ tsp salt"
        result = normalize_ingredient_input(text)
        lines = result.strip().splitlines()
        assert len(lines) == 2

    def test_decimal_also_converted(self):
        result = normalize_ingredient_input("0.5 cup flour")
        assert "1/2" in result


# ---------------------------------------------------------------------------
# format_instructions_for_display
# ---------------------------------------------------------------------------

class TestFormatInstructionsForDisplay:
    def test_plain_lines_become_bullets(self):
        text = "Preheat oven.\nMix ingredients.\nBake 30 minutes."
        result = format_instructions_for_display(text)
        for line in result.splitlines():
            assert line.startswith("- ")

    def test_already_bulleted_unchanged(self):
        text = "- Step one\n- Step two"
        result = format_instructions_for_display(text)
        assert result == text

    def test_numbered_list_unchanged(self):
        text = "1. Preheat oven\n2. Mix batter"
        result = format_instructions_for_display(text)
        assert result == text

    def test_empty_string(self):
        assert format_instructions_for_display("") == ""

    def test_non_string_returns_empty(self):
        assert format_instructions_for_display(None) == ""  # type: ignore[arg-type]

    def test_whitespace_only(self):
        assert format_instructions_for_display("   ") == ""

    def test_mixed_leading_whitespace_stripped(self):
        text = "  Step one  \n  Step two  "
        result = format_instructions_for_display(text)
        assert "Step one" in result
        assert "Step two" in result
