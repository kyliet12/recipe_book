import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction


def decimal_to_mixed_fraction(value: str) -> str:
    """Convert a decimal string to a mixed fraction (e.g., 1.5 -> 1 1/2)."""
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        return value

    if number == number.to_integral_value():
        return str(int(number))

    sign = "-" if number < 0 else ""
    abs_number = abs(number)
    fraction = Fraction(abs_number).limit_denominator(16)

    whole = fraction.numerator // fraction.denominator
    remainder = fraction.numerator % fraction.denominator

    if remainder == 0:
        return f"{sign}{whole}"
    if whole == 0:
        return f"{sign}{remainder}/{fraction.denominator}"
    return f"{sign}{whole} {remainder}/{fraction.denominator}"


def format_ingredients_for_display(ingredients_text: str) -> str:
    """Convert decimal quantities in ingredient lines to fractions for display."""
    if not isinstance(ingredients_text, str):
        return ""

    decimal_pattern = re.compile(r"(?<!\d)(\d*\.\d+)(?!\d)")

    def convert_line(line: str) -> str:
        return decimal_pattern.sub(lambda m: decimal_to_mixed_fraction(m.group(1)), line)

    return "\n".join(convert_line(line) for line in ingredients_text.splitlines())


def normalize_ingredient_input(ingredients_text: str) -> str:
    """Normalize ingredient input so fractions are consistently supported."""
    if not isinstance(ingredients_text, str):
        return ""

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

    normalized_lines = []
    for raw_line in ingredients_text.splitlines():
        line = raw_line.replace("⁄", "/")
        for char, ascii_fraction in fraction_map.items():
            line = re.sub(rf"(\d){re.escape(char)}", rf"\1 {ascii_fraction}", line)
            line = line.replace(char, ascii_fraction)
        normalized_lines.append(line)

    return format_ingredients_for_display("\n".join(normalized_lines))


def format_instructions_for_display(instructions_text: str) -> str:
    """Return instructions as markdown bullets when the text is plain paragraphs/lines."""
    if not isinstance(instructions_text, str):
        return ""

    cleaned = instructions_text.strip()
    if not cleaned:
        return ""

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return ""

    bullet_or_numbered = re.compile(r"^([\-*+]\s+|\d+[.)]\s+)")
    if all(bullet_or_numbered.match(line) for line in lines):
        return "\n".join(lines)

    return "\n".join(f"- {line}" for line in lines)
