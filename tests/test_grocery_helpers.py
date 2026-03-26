"""Tests for grocery_helpers.py."""

from fractions import Fraction

import pytest
from grocery_helpers import (
    build_grocery_list,
    classify_ingredient,
    fraction_text_to_ascii,
    normalize_unit,
    parse_ingredient_line,
    parse_quantity_token,
    quantity_to_display,
)


# ---------------------------------------------------------------------------
# fraction_text_to_ascii
# ---------------------------------------------------------------------------

class TestFractionTextToAscii:
    def test_half_symbol(self):
        assert fraction_text_to_ascii("½ cup") == "1/2 cup"

    def test_quarter_symbol(self):
        assert fraction_text_to_ascii("¼ tsp") == "1/4 tsp"

    def test_digit_adjacent(self):
        assert fraction_text_to_ascii("1½") == "1 1/2"

    def test_unicode_slash_normalized(self):
        assert fraction_text_to_ascii("1⁄2") == "1/2"

    def test_no_fractions_unchanged(self):
        assert fraction_text_to_ascii("2 cups flour") == "2 cups flour"


# ---------------------------------------------------------------------------
# parse_quantity_token
# ---------------------------------------------------------------------------

class TestParseQuantityToken:
    def test_integer(self):
        assert parse_quantity_token("2") == Fraction(2)

    def test_fraction(self):
        assert parse_quantity_token("1/2") == Fraction(1, 2)

    def test_decimal(self):
        assert parse_quantity_token("0.5") == Fraction(1, 2)

    def test_non_numeric_returns_none(self):
        assert parse_quantity_token("cup") is None

    def test_empty_returns_none(self):
        assert parse_quantity_token("") is None

    def test_range_takes_lower_bound(self):
        assert parse_quantity_token("2-3") == Fraction(2)


# ---------------------------------------------------------------------------
# quantity_to_display
# ---------------------------------------------------------------------------

class TestQuantityToDisplay:
    def test_whole(self):
        assert quantity_to_display(Fraction(3)) == "3"

    def test_half(self):
        assert quantity_to_display(Fraction(1, 2)) == "1/2"

    def test_mixed(self):
        assert quantity_to_display(Fraction(3, 2)) == "1 1/2"

    def test_negative(self):
        assert quantity_to_display(Fraction(-1, 2)) == "-1/2"


# ---------------------------------------------------------------------------
# normalize_unit
# ---------------------------------------------------------------------------

class TestNormalizeUnit:
    def test_cups_to_cup(self):
        assert normalize_unit("cups") == "cup"

    def test_tablespoons(self):
        assert normalize_unit("tablespoons") == "tbsp"

    def test_teaspoon(self):
        assert normalize_unit("teaspoon") == "tsp"

    def test_ounces(self):
        assert normalize_unit("ounces") == "oz"

    def test_pounds(self):
        assert normalize_unit("pounds") == "lb"

    def test_unknown_unit_lowercased(self):
        assert normalize_unit("PINCH") == "pinch"

    def test_trailing_period_stripped(self):
        assert normalize_unit("cup.") == "cup"


# ---------------------------------------------------------------------------
# parse_ingredient_line
# ---------------------------------------------------------------------------

class TestParseIngredientLine:
    def test_simple_quantity_unit_name(self):
        result = parse_ingredient_line("2 cups flour")
        assert result is not None
        qty, unit, name = result
        assert qty == Fraction(2)
        assert unit == "cup"
        assert name == "flour"

    def test_fraction_quantity(self):
        result = parse_ingredient_line("1/2 tsp salt")
        assert result is not None
        qty, unit, name = result
        assert qty == Fraction(1, 2)
        assert unit == "tsp"
        assert name == "salt"

    def test_mixed_number(self):
        result = parse_ingredient_line("1 1/2 cups milk")
        assert result is not None
        qty, unit, name = result
        assert qty == Fraction(3, 2)
        assert unit == "cup"
        assert name == "milk"

    def test_no_unit(self):
        result = parse_ingredient_line("3 eggs")
        assert result is not None
        qty, unit, name = result
        assert qty == Fraction(3)
        assert unit == ""
        assert "egg" in name

    def test_empty_line_returns_none(self):
        assert parse_ingredient_line("") is None
        assert parse_ingredient_line("   ") is None

    def test_unicode_fraction(self):
        result = parse_ingredient_line("½ cup sugar")
        assert result is not None
        qty, unit, name = result
        assert qty == Fraction(1, 2)
        assert unit == "cup"
        assert "sugar" in name

    def test_parenthetical_removed(self):
        result = parse_ingredient_line("1 cup (packed) brown sugar")
        assert result is not None
        _, _, name = result
        assert "packed" not in name

    def test_bullet_prefix_removed(self):
        result = parse_ingredient_line("- 2 tbsp butter")
        assert result is not None
        qty, unit, name = result
        assert qty == Fraction(2)
        assert unit == "tbsp"
        assert "butter" in name


# ---------------------------------------------------------------------------
# classify_ingredient
# ---------------------------------------------------------------------------

class TestClassifyIngredient:
    def test_produce(self):
        assert classify_ingredient("garlic") == "Produce"

    def test_meat(self):
        assert classify_ingredient("chicken breast") == "Meat"

    def test_dairy(self):
        assert classify_ingredient("cheddar cheese") == "Dairy"

    def test_spices(self):
        assert classify_ingredient("cumin") == "Spices"

    def test_dry_goods(self):
        assert classify_ingredient("all-purpose flour") == "Dry Goods"

    def test_unknown_goes_to_other(self):
        assert classify_ingredient("xanthan gum") == "Other"


# ---------------------------------------------------------------------------
# build_grocery_list
# ---------------------------------------------------------------------------

class TestBuildGroceryList:
    def _recipe(self, ingredients: str) -> dict:
        return {"name": "Test", "ingredients": ingredients}

    def test_single_recipe(self):
        recipes = [self._recipe("2 cups flour\n1 tsp salt")]
        result = build_grocery_list(recipes)
        assert isinstance(result, dict)
        all_lines = [line for lines in result.values() for line in lines]
        assert any("flour" in line for line in all_lines)
        assert any("salt" in line for line in all_lines)

    def test_quantities_combined(self):
        r1 = self._recipe("1 cup sugar")
        r2 = self._recipe("1 cup sugar")
        result = build_grocery_list([r1, r2])
        all_lines = [line for lines in result.values() for line in lines]
        # Should combine to 2 cups
        assert any("2" in line and "sugar" in line for line in all_lines)

    def test_empty_recipes_list(self):
        assert build_grocery_list([]) == {}

    def test_recipe_with_no_ingredients(self):
        result = build_grocery_list([{"name": "Empty", "ingredients": ""}])
        assert result == {}

    def test_non_string_ingredients_skipped(self):
        result = build_grocery_list([{"name": "Bad", "ingredients": 42}])
        assert result == {}

    def test_categories_present(self):
        recipes = [self._recipe("1 cup milk\n2 chicken breasts\n1 tsp salt")]
        result = build_grocery_list(recipes)
        assert "Dairy" in result or "Meat" in result or "Spices" in result
