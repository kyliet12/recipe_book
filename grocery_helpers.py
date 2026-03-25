import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction


def fraction_text_to_ascii(text: str) -> str:
    """Convert unicode fraction symbols into ascii fractions for parsing."""
    fraction_map = {
        "¼": "1/4",
        "½": "1/2",
        "¾": "3/4",
        "⅐": "1/7",
        "⅑": "1/9",
        "⅒": "1/10",
        "⅓": "1/3",
        "⅔": "2/3",
        "⅕": "1/5",
        "⅖": "2/5",
        "⅗": "3/5",
        "⅘": "4/5",
        "⅙": "1/6",
        "⅚": "5/6",
        "⅛": "1/8",
        "⅜": "3/8",
        "⅝": "5/8",
        "⅞": "7/8",
    }

    normalized = text.replace("⁄", "/")
    for symbol, ascii_fraction in fraction_map.items():
        normalized = re.sub(rf"(\d){re.escape(symbol)}", rf"\1 {ascii_fraction}", normalized)
        normalized = normalized.replace(symbol, ascii_fraction)
    return normalized


def parse_quantity_token(token: str) -> Fraction | None:
    """Parse a token into a Fraction if it looks like a quantity."""
    clean = token.strip().lower().replace("(", "").replace(")", "")
    if not clean:
        return None

    if "-" in clean and "/" not in clean:
        clean = clean.split("-", 1)[0]

    if "/" in clean:
        parts = clean.split("/", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() and int(parts[1]) != 0:
            return Fraction(int(parts[0]), int(parts[1]))
        return None

    try:
        return Fraction(Decimal(clean)).limit_denominator(16)
    except (InvalidOperation, ValueError):
        return None


def quantity_to_display(value: Fraction) -> str:
    """Format a Fraction as an easy-to-read whole/mixed fraction."""
    sign = "-" if value < 0 else ""
    abs_value = abs(value)
    whole = abs_value.numerator // abs_value.denominator
    remainder = abs_value.numerator % abs_value.denominator

    if remainder == 0:
        return f"{sign}{whole}"
    if whole == 0:
        return f"{sign}{remainder}/{abs_value.denominator}"
    return f"{sign}{whole} {remainder}/{abs_value.denominator}"


def normalize_unit(unit: str) -> str:
    """Normalize unit synonyms so quantities can be combined reliably."""
    unit_aliases = {
        "c": "cup",
        "cups": "cup",
        "cup": "cup",
        "tsp": "tsp",
        "teaspoon": "tsp",
        "teaspoons": "tsp",
        "tbsp": "tbsp",
        "tablespoon": "tbsp",
        "tablespoons": "tbsp",
        "oz": "oz",
        "ounce": "oz",
        "ounces": "oz",
        "lb": "lb",
        "lbs": "lb",
        "pound": "lb",
        "pounds": "lb",
        "g": "g",
        "gram": "g",
        "grams": "g",
        "kg": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
        "ml": "ml",
        "l": "l",
        "liter": "l",
        "liters": "l",
        "clove": "clove",
        "cloves": "clove",
        "can": "can",
        "cans": "can",
        "package": "package",
        "packages": "package",
        "pkg": "package",
        "stick": "stick",
        "sticks": "stick",
        "pinch": "pinch",
        "dash": "dash",
    }
    return unit_aliases.get(unit.lower().strip().rstrip("."), unit.lower().strip().rstrip("."))


def classify_ingredient(name: str) -> str:
    """Assign an ingredient category for grocery-list grouping."""
    n = name.lower()

    categories = {
        "Produce": [
            "onion", "garlic", "tomato", "spinach", "lettuce", "carrot", "celery",
            "pepper", "zucchini", "broccoli", "cauliflower", "potato", "lemon", "lime",
            "apple", "banana", "berry", "avocado", "cilantro", "parsley", "ginger",
        ],
        "Meat": [
            "chicken", "beef", "pork", "turkey", "bacon", "sausage", "ham", "steak",
            "ground", "salmon", "shrimp", "fish",
        ],
        "Dairy": [
            "milk", "cream", "butter", "cheese", "yogurt", "parmesan", "mozzarella",
            "cheddar", "egg", "eggs",
        ],
        "Spices": [
            "salt", "pepper", "oregano", "paprika", "cumin", "coriander", "turmeric",
            "chili", "cinnamon", "nutmeg", "garlic powder", "onion powder", "seasoning",
        ],
        "Frozen": ["frozen", "ice cream"],
        "Dry Goods": [
            "flour", "sugar", "oats", "rice", "pasta", "beans", "lentils", "honey",
            "oil", "vinegar", "broth", "stock", "chocolate", "peanut butter", "vanilla",
        ],
    }

    for category, keywords in categories.items():
        if any(keyword in n for keyword in keywords):
            return category
    return "Other"


def parse_ingredient_line(line: str) -> tuple[Fraction | None, str, str] | None:
    """Parse one ingredient line into quantity, normalized unit, and name."""
    text = fraction_text_to_ascii(line.strip())
    if not text:
        return None

    text = re.sub(r"^[\-•*\s]+", "", text)
    text = re.sub(r"\([^)]*\)", "", text).strip()
    tokens = text.split()
    if not tokens:
        return None

    quantity: Fraction | None = None
    consumed = 0

    first = parse_quantity_token(tokens[0])
    if first is not None:
        quantity = first
        consumed = 1
        if len(tokens) > 1:
            second = parse_quantity_token(tokens[1])
            if second is not None and "/" in tokens[1]:
                quantity += second
                consumed = 2

    unit = ""
    if len(tokens) > consumed:
        candidate_unit = normalize_unit(tokens[consumed])
        known_units = {
            "cup", "tsp", "tbsp", "oz", "lb", "g", "kg", "ml", "l", "clove", "can",
            "package", "stick", "pinch", "dash",
        }
        if candidate_unit in known_units:
            unit = candidate_unit
            consumed += 1

    name = " ".join(tokens[consumed:]).strip().lower()
    name = re.sub(r"^of\s+", "", name)
    name = re.sub(r"\s+", " ", name)

    if not name:
        name = text.lower()

    return quantity, unit, name


def build_grocery_list(recipes: list[dict]) -> dict[str, list[str]]:
    """Combine recipe ingredients into categorized grocery-list lines."""
    totals: dict[tuple[str, str, str], Fraction | None] = {}

    for recipe in recipes:
        ingredients_text = recipe.get("ingredients", "")
        if not isinstance(ingredients_text, str):
            continue

        for raw_line in ingredients_text.splitlines():
            parsed = parse_ingredient_line(raw_line)
            if parsed is None:
                continue

            quantity, unit, name = parsed
            category = classify_ingredient(name)
            key = (category, name, unit)

            if key not in totals:
                totals[key] = quantity
            else:
                existing = totals[key]
                if existing is None:
                    totals[key] = quantity
                elif quantity is not None:
                    totals[key] = existing + quantity

    grouped: dict[str, list[str]] = defaultdict(list)
    for (category, name, unit), quantity in sorted(totals.items()):
        display_name = name
        if quantity is None:
            line = display_name
        else:
            qty_text = quantity_to_display(quantity)
            line = f"{qty_text} {unit} {display_name}".strip()
            line = re.sub(r"\s+", " ", line)
        grouped[category].append(line)

    return dict(grouped)
