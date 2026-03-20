import json
import os
import re
import html
from collections import defaultdict
from pathlib import Path
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from urllib.parse import urlparse, urlencode
from typing import Any, Callable
from uuid import uuid4

import requests
import streamlit as st
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import (
    ElementNotFoundInHtml,
    FieldNotProvidedByWebsiteException,
    NoSchemaFoundInWildMode,
    WebsiteNotImplementedError,
)

DATA_FILE = "recipes.json"
IMAGE_DIR = "images"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data() -> dict:
    """Load recipe book data from the JSON file, or return defaults."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"folders": ["Desserts", "Snacks", "Main Dishes", "Drinks"], "recipes": []}


def save_data(data: dict) -> None:
    """Persist recipe book data to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_uploaded_image(uploaded_image: Any) -> str:
    """Save an uploaded image in the local images folder and return its path."""
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    image_dir = Path(IMAGE_DIR)
    image_dir.mkdir(parents=True, exist_ok=True)

    original_name = Path(str(getattr(uploaded_image, "name", ""))).name
    suffix = Path(original_name).suffix.lower()

    if suffix not in allowed_suffixes:
        raise ValueError("Unsupported image type. Please upload PNG, JPG, JPEG, GIF, or WEBP.")

    stem = Path(original_name).stem
    safe_stem = "".join(ch for ch in stem if ch.isalnum() or ch in ("_", "-")).strip("_-")
    if not safe_stem:
        safe_stem = "recipe"

    filename = f"{safe_stem}_{uuid4().hex[:8]}{suffix}"
    file_path = image_dir / filename
    file_path.write_bytes(bytes(uploaded_image.getbuffer()))
    return file_path.as_posix()


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


def recipe_anchor_id(recipe: dict, idx: int) -> str:
    """Build a stable-ish anchor id for recipe cards/details."""
    name = str(recipe.get("name", "recipe")).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "recipe"
    return f"recipe-detail-{slug}-{idx}"


def get_query_param_value(name: str) -> str:
    """Return a query param as a single string value."""
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def render_recipe_thumbnail_grid(folder_recipes: list[dict], folder: str) -> None:
    """Render a responsive thumbnail grid that adapts column count to window width."""
    st.markdown(
        """
        <style>
            .recipe-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 0.9rem;
                margin: 0.5rem 0 1rem 0;
            }
            .recipe-card {
                display: block;
                text-decoration: none;
                color: inherit;
                border: 1px solid rgba(128, 128, 128, 0.35);
                border-radius: 0.75rem;
                overflow: hidden;
                background: rgba(255, 255, 255, 0.02);
            }
            .recipe-card:hover {
                border-color: rgba(255, 75, 75, 0.6);
            }
            .recipe-card img,
            .recipe-card .recipe-thumb-placeholder {
                width: 100%;
                aspect-ratio: 4 / 3;
                object-fit: cover;
                display: block;
            }
            .recipe-thumb-placeholder {
                background: rgba(200, 200, 200, 0.15);
                color: rgba(120, 120, 120, 0.95);
                display: grid;
                place-items: center;
                font-size: 0.85rem;
            }
            .recipe-card-title {
                padding: 0.55rem 0.7rem 0.65rem 0.7rem;
                font-weight: 600;
                font-size: 0.92rem;
                line-height: 1.25;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    cards: list[str] = []
    for idx, recipe in enumerate(folder_recipes):
        title = html.escape(str(recipe.get("name", "Recipe")))
        anchor = recipe_anchor_id(recipe, idx)
        image = str(recipe.get("image", "")).strip()
        query = urlencode({"page": "recipe", "folder": folder, "recipe": anchor})

        if image:
            thumb = f"<img src=\"{html.escape(image)}\" alt=\"{title}\" />"
        else:
            thumb = "<div class='recipe-thumb-placeholder'>No image</div>"

        cards.append(
            (
                f"<a class='recipe-card' href='?{query}' target='_self'>"
                f"{thumb}"
                f"<div class='recipe-card-title'>{title}</div>"
                "</a>"
            )
        )

    st.markdown(f"<div class='recipe-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Scraping helper
# ---------------------------------------------------------------------------

def scrape_recipe_from_url(url: str) -> dict:
    """
    Try to scrape recipe details from *url*.

    Returns a dict with recipe fields on success, or raises an exception with
    a human-readable message on failure.
    """
    # Validate URL scheme to prevent SSRF against internal services
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http:// and https:// URLs are supported.")
    if not parsed.netloc:
        raise ValueError("Invalid URL – no hostname found.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise ValueError("Could not connect to the website. Check the URL and try again.")
    except requests.exceptions.Timeout:
        raise ValueError("The request timed out. The website may be slow or unavailable.")
    except requests.exceptions.HTTPError as exc:
        raise ValueError(f"The website returned an error: {exc}")
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"Failed to fetch the URL: {exc}")

    try:
        scraper = scrape_html(response.text, org_url=url, wild_mode=True)
    except (NoSchemaFoundInWildMode, WebsiteNotImplementedError):
        raise ValueError(
            "Could not extract recipe data from this website. "
            "The site may not use a supported recipe format."
        )
    except Exception as exc:
        raise ValueError(f"An error occurred while parsing the recipe: {exc}")

    def safe_get(fn: Callable[[], Any], default: Any = "") -> Any:
        try:
            val = fn()
            return val if val else default
        except (ElementNotFoundInHtml, FieldNotProvidedByWebsiteException, Exception):
            return default

    ingredients_raw = safe_get(scraper.ingredients, "")
    if isinstance(ingredients_raw, list):
        ingredients = "\n".join(str(item) for item in ingredients_raw)
    elif isinstance(ingredients_raw, str):
        ingredients = ingredients_raw
    else:
        ingredients = ""

    instructions = safe_get(scraper.instructions, "")

    return {
        "name": safe_get(scraper.title, ""),
        "description": "",
        "image": safe_get(scraper.image, ""),
        "servings": str(safe_get(scraper.yields, "")),
        "prep_time": str(safe_get(scraper.prep_time, "")),
        "cook_time": str(safe_get(scraper.cook_time, "")),
        "ingredients": ingredients,
        "instructions": instructions,
        "source_url": url,
        "folder": "",
    }


# ---------------------------------------------------------------------------
# Streamlit pages
# ---------------------------------------------------------------------------

def show_home(data: dict) -> None:
    """Landing page – list all folders and a summary of recipes in each."""
    st.title("Our Recipe Book")
    st.write("Welcome! Use the sidebar to navigate the website. You can add new recipes, search recipes, or create a grocery list.")
    if not data["folders"]:
        st.info("No folders yet. Create a folder from the sidebar to get started.")
        return

    cols = st.columns(3)
    for idx, folder in enumerate(data["folders"]):
        count = sum(1 for r in data["recipes"] if r.get("folder") == folder)
        with cols[idx % 3]:
            if st.button(f"📁 {folder}\n\n*{count} recipe{'s' if count != 1 else ''}*",
                         key=f"home_folder_{folder}", use_container_width=True):
                st.session_state.page = "browse"
                st.session_state.selected_folder = folder
                st.rerun()


def show_browse(data: dict) -> None:
    """Browse recipes in the currently selected folder."""
    folder = st.session_state.get("selected_folder", "")
    st.title(f"{folder}")

    nav_cols = st.columns(2)
    with nav_cols[0]:
        if st.button("← Back to Home", key="back_to_home"):
            st.session_state.page = "home"
            st.query_params.clear()
            st.query_params["page"] = "home"
            st.rerun()
    
    # with nav_cols[1]:
    #     if st.button("➕ Add Recipe", key="add_recipe_in_folder", use_container_width=True):
    #         st.session_state.page = "add_recipe"
    #         st.rerun()

    folder_recipes = [r for r in data["recipes"] if r.get("folder") == folder]

    if not folder_recipes:
        st.info(f"No recipes in '{folder}' yet. Add one using the sidebar!")
        return

    render_recipe_thumbnail_grid(folder_recipes, folder)
    st.subheader("Recipe Details")

    for i, recipe in enumerate(folder_recipes):
        anchor_id = recipe_anchor_id(recipe, i)
        st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            top_cols = st.columns([1, 4])

            with top_cols[0]:
                if recipe.get("image"):
                    st.image(recipe["image"], width=120)
                else:
                    st.caption("No image")

            with top_cols[1]:
                st.markdown(f"### {recipe['name']}")
                if recipe.get("tags"):
                    tags_display = ", ".join([f"🏷️ {tag}" for tag in recipe.get("tags", [])])
                    st.caption(tags_display)

            with st.expander("View recipe details", expanded=False):
                if recipe.get("image"):
                    st.image(recipe["image"], use_container_width=True)

                if recipe.get("description"):
                    st.markdown(f"*{recipe['description']}*")

                meta_cols = st.columns(3)
                if recipe.get("servings"):
                    meta_cols[0].metric("Servings", recipe["servings"])
                if recipe.get("prep_time"):
                    meta_cols[1].metric("Prep Time", recipe["prep_time"])
                if recipe.get("cook_time"):
                    meta_cols[2].metric("Cook Time", recipe["cook_time"])

                if recipe.get("ingredients"):
                    st.subheader("Ingredients")
                    st.text(format_ingredients_for_display(recipe["ingredients"]))

                if recipe.get("instructions"):
                    st.subheader("Instructions")
                    st.markdown(format_instructions_for_display(recipe["instructions"]))

                if recipe.get("source_url"):
                    st.markdown(f"[🔗 Original recipe]({recipe['source_url']})")

                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button("✏️ Edit recipe", key=f"edit_{folder}_{i}", use_container_width=True):
                        global_idx = data["recipes"].index(recipe)
                        st.session_state.edit_recipe_index = global_idx
                        st.session_state.page = "edit_recipe"
                        st.rerun()

                with action_cols[1]:
                    if st.button("🗑️ Delete recipe", key=f"delete_{folder}_{i}", use_container_width=True):
                        global_idx = data["recipes"].index(recipe)
                        data["recipes"].pop(global_idx)
                        save_data(data)
                        st.success(f"Deleted '{recipe['name']}'.")
                        st.rerun()


def show_recipe_detail(data: dict) -> None:
    """Show a single recipe selected from query params."""
    folder = get_query_param_value("folder")
    selected_anchor = get_query_param_value("recipe")

    if not folder or not selected_anchor:
        st.warning("No recipe selected.")
        return

    folder_recipes = [r for r in data["recipes"] if r.get("folder") == folder]

    selected_recipe: dict | None = None
    selected_idx = -1
    for i, recipe in enumerate(folder_recipes):
        if recipe_anchor_id(recipe, i) == selected_anchor:
            selected_recipe = recipe
            selected_idx = i
            break

    if selected_recipe is None:
        st.warning("That recipe could not be found.")
        return

    st.title(f"🍽️ {selected_recipe.get('name', 'Recipe')}")
    st.caption(f"Folder: {folder}")
    if selected_recipe.get("tags"):
        tags_display = ", ".join([f"🏷️ {tag}" for tag in selected_recipe.get("tags", [])])
        st.caption(tags_display)

    if st.button(f"← Back to {folder}", key=f"back_to_folder_{folder}"):
        st.session_state.page = "browse"
        st.session_state.selected_folder = folder
        st.query_params.clear()
        st.query_params["page"] = "browse"
        st.query_params["folder"] = folder
        st.rerun()

    if selected_recipe.get("image"):
        st.image(selected_recipe["image"], use_container_width=True)

    if selected_recipe.get("description"):
        st.markdown(f"*{selected_recipe['description']}*")

    meta_cols = st.columns(3)
    if selected_recipe.get("servings"):
        meta_cols[0].metric("Servings", selected_recipe["servings"])
    if selected_recipe.get("prep_time"):
        meta_cols[1].metric("Prep Time", selected_recipe["prep_time"])
    if selected_recipe.get("cook_time"):
        meta_cols[2].metric("Cook Time", selected_recipe["cook_time"])

    if selected_recipe.get("ingredients"):
        st.subheader("Ingredients")
        st.text(format_ingredients_for_display(selected_recipe["ingredients"]))

    if selected_recipe.get("instructions"):
        st.subheader("Instructions")
        st.markdown(format_instructions_for_display(selected_recipe["instructions"]))

    if selected_recipe.get("source_url"):
        st.markdown(f"[🔗 Original recipe]({selected_recipe['source_url']})")

    st.divider()
    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("✏️ Edit recipe", key=f"edit_single_{folder}_{selected_idx}", use_container_width=True):
            global_idx = data["recipes"].index(selected_recipe)
            st.session_state.edit_recipe_index = global_idx
            st.session_state.page = "edit_recipe"
            st.rerun()
    
    with action_cols[1]:
        if st.button("🗑️ Delete recipe", key=f"delete_single_{folder}_{selected_idx}", use_container_width=True):
            global_idx = data["recipes"].index(selected_recipe)
            data["recipes"].pop(global_idx)
            save_data(data)
            st.success("Recipe deleted.")
            st.query_params.clear()
            st.query_params["page"] = "browse"
            st.query_params["folder"] = folder
            st.rerun()


def show_grocery_list(data: dict) -> None:
    """Build a grocery list from selected recipes."""
    st.title("🛒 Grocery List")

    if "grocery_list_items" not in st.session_state:
        st.session_state.grocery_list_items = {}
    if "grocery_list_checked" not in st.session_state:
        st.session_state.grocery_list_checked = {}
    if "grocery_list_edits" not in st.session_state:
        st.session_state.grocery_list_edits = {}

    if not data.get("recipes"):
        st.info("No recipes found yet. Add recipes first to build a grocery list.")
        return

    recipe_labels = []
    recipe_lookup: dict[str, dict] = {}
    for idx, recipe in enumerate(data["recipes"]):
        name = str(recipe.get("name", f"Recipe {idx + 1}"))
        folder = str(recipe.get("folder", "Unsorted"))
        label = f"{name} ({folder})"
        # Keep labels unique when names/folders repeat.
        if label in recipe_lookup:
            label = f"{label} #{idx + 1}"
        recipe_labels.append(label)
        recipe_lookup[label] = recipe

    selected_labels = st.multiselect(
        "Select recipes to include",
        options=recipe_labels,
        default=recipe_labels,
    )

    if not selected_labels:
        st.warning("Select at least one recipe to generate a grocery list.")
        return

    selected_recipes = [recipe_lookup[label] for label in selected_labels]
    grocery = build_grocery_list(selected_recipes)

    if not grocery:
        st.warning("No ingredients could be parsed from the selected recipes.")
        return

    st.session_state.grocery_list_items = grocery
    for category, items in grocery.items():
        for item in items:
            item_key = f"{category}:{item}"
            if item_key not in st.session_state.grocery_list_checked:
                st.session_state.grocery_list_checked[item_key] = False
            if item_key not in st.session_state.grocery_list_edits:
                st.session_state.grocery_list_edits[item_key] = item

    category_order = ["Produce", "Meat", "Dairy", "Spices", "Dry Goods", "Frozen", "Other"]
    st.caption("Matching ingredients with the same unit are combined automatically.")

    st.divider()
    st.subheader("Interactive Grocery List")

    items_to_remove: set[str] = set()

    for category in category_order:
        items = grocery.get(category, [])
        
        # Initialize custom items for each category if not present
        if f"custom_{category}" not in st.session_state:
            st.session_state[f"custom_{category}"] = []

        with st.container(border=True):
            st.subheader(category)

            if not items and not st.session_state[f"custom_{category}"]:
                st.caption("No items yet. Add one below!")

            for idx, original_item in enumerate(items):
                item_key = f"{category}:{original_item}"
                is_checked = st.session_state.grocery_list_checked.get(item_key, False)
                current_text = st.session_state.grocery_list_edits.get(item_key, original_item)

                col1, col2, col3, col4 = st.columns([0.5, 8, 1, 0.5])

                with col1:
                    new_checked = st.checkbox(
                        "Done",
                        value=is_checked,
                        key=f"check_{category}_{idx}",
                        label_visibility="collapsed",
                    )
                    st.session_state.grocery_list_checked[item_key] = new_checked

                with col2:
                    edited_item = st.text_input(
                        "Item",
                        value=current_text,
                        key=f"edit_{category}_{idx}",
                        label_visibility="collapsed",
                        disabled=is_checked,
                    )
                    st.session_state.grocery_list_edits[item_key] = edited_item

                with col3:
                    if st.button("✕", key=f"remove_{category}_{idx}", help="Remove item"):
                        items_to_remove.add(item_key)

                with col4:
                    if is_checked:
                        st.caption("✓")

            st.divider()
            col_add1, col_add2 = st.columns([8, 1])
            with col_add1:
                new_item = st.text_input(
                    "Add new item",
                    key=f"add_item_{category}",
                    label_visibility="collapsed",
                    placeholder=f"Add item to {category}...",
                )
            with col_add2:
                if st.button("➕", key=f"add_btn_{category}", help="Add item"):
                    if new_item.strip():
                        new_item_key = f"{category}:{new_item.strip()}"
                        if new_item_key not in st.session_state.grocery_list_checked:
                            st.session_state.grocery_list_checked[new_item_key] = False
                            st.session_state.grocery_list_edits[new_item_key] = new_item.strip()
                            st.session_state.grocery_list_items.setdefault(category, []).append(new_item.strip())
                            st.rerun()

        st.divider()

    st.subheader("Export")
    export_lines: list[str] = []
    for category in category_order:
        items = st.session_state.grocery_list_items.get(category, [])
        if not items:
            continue

        export_lines.append(f"### {category}")
        for original_item in items:
            item_key = f"{category}:{original_item}"
            if item_key in items_to_remove:
                continue
            display_item = st.session_state.grocery_list_edits.get(item_key, original_item)
            is_checked = st.session_state.grocery_list_checked.get(item_key, False)
            prefix = "[x]" if is_checked else "[ ]"
            export_lines.append(f"{prefix} {display_item}")
        export_lines.append("")

    if export_lines:
        st.download_button(
            "Download Grocery List",
            data="\n".join(export_lines).strip(),
            file_name="grocery_list.txt",
            mime="text/plain",
            use_container_width=True,
        )


def show_add_recipe(data: dict) -> None:
    """Form to add a new recipe (manual or via URL)."""
    st.title("➕ Add New Recipe")

    method = st.radio(
        "How would you like to add the recipe?",
        ["Enter details manually", "Import from a website URL"],
        horizontal=True,
    )

    prefill: dict = {}

    if method == "Import from a website URL":
        url_input = st.text_input("Recipe URL", placeholder="https://www.example.com/recipe/...")
        if st.button("Fetch Recipe"):
            if not url_input.strip():
                st.error("Please enter a URL.")
            else:
                with st.spinner("Fetching recipe from the website…"):
                    try:
                        prefill = scrape_recipe_from_url(url_input.strip())
                        st.success("Recipe details fetched! Review and save below.")
                        st.session_state.prefill = prefill
                    except ValueError as exc:
                        st.error(f"⚠️ {exc}")
                        st.session_state.prefill = {}
        prefill = st.session_state.get("prefill", {})

    st.divider()
    st.subheader("Recipe Details")

    with st.form("recipe_form"):
        name = st.text_input("Recipe Name *", value=prefill.get("name", ""))
        description = st.text_area("Description", value=prefill.get("description", ""), height=80)
        image = st.text_input(
            "Image URL or local path",
            value=prefill.get("image", ""),
            placeholder="https://example.com/recipe-image.jpg",
        )
        uploaded_image = st.file_uploader(
            "Or upload an image file (saved to local images folder)",
            type=["png", "jpg", "jpeg", "gif", "webp"],
            accept_multiple_files=False,
        )

        folder_options = data["folders"] if data["folders"] else ["(no folders – create one first)"]
        default_folder = prefill.get("folder", "")
        default_idx = folder_options.index(default_folder) if default_folder in folder_options else 0
        folder = st.selectbox("Folder *", folder_options, index=default_idx)

        col1, col2, col3 = st.columns(3)
        servings = col1.text_input("Servings", value=prefill.get("servings", ""))
        prep_time = col2.text_input("Prep Time", value=prefill.get("prep_time", ""),
                                    placeholder="e.g. 15 minutes")
        cook_time = col3.text_input("Cook Time", value=prefill.get("cook_time", ""),
                                    placeholder="e.g. 30 minutes")

        ingredients = st.text_area(
            "Ingredients (one per line) *",
            value=prefill.get("ingredients", ""),
            height=150,
            help="Fractions are supported (for example 1/2 cup or 1 1/2 tsp).",
        )
        instructions = st.text_area(
            "Instructions *",
            value=prefill.get("instructions", ""),
            height=200,
        )
        source_url = st.text_input("Source URL (optional)", value=prefill.get("source_url", ""))
        tags_input = st.text_input(
            "Tags (comma-separated) - e.g. soup, crock pot, sheet pan, bowl",
            value=", ".join(prefill.get("tags", [])),
            placeholder="e.g. soup, quick, vegetarian"
        )

        submitted = st.form_submit_button("💾 Save Recipe", use_container_width=True)

    if submitted:
        name_clean = name.strip() if isinstance(name, str) else ""
        description_clean = description.strip() if isinstance(description, str) else ""
        image_clean = image.strip() if isinstance(image, str) else ""
        servings_clean = servings.strip() if isinstance(servings, str) else ""
        prep_time_clean = prep_time.strip() if isinstance(prep_time, str) else ""
        cook_time_clean = cook_time.strip() if isinstance(cook_time, str) else ""
        ingredients_clean = normalize_ingredient_input(ingredients.strip()) if isinstance(ingredients, str) else ""
        instructions_clean = instructions.strip() if isinstance(instructions, str) else ""
        source_url_clean = source_url.strip() if isinstance(source_url, str) else ""
        tags_clean = [tag.strip().lower() for tag in tags_input.split(",") if tag.strip()] if isinstance(tags_input, str) else []

        if uploaded_image is not None:
            try:
                image_clean = save_uploaded_image(uploaded_image)
            except ValueError as exc:
                st.error(str(exc))
                return

        errors = []
        if not name_clean:
            errors.append("Recipe Name is required.")
        if not ingredients_clean:
            errors.append("Ingredients are required.")
        if not instructions_clean:
            errors.append("Instructions are required.")
        if folder == "(no folders – create one first)":
            errors.append("Please create a folder before adding a recipe.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            recipe = {
                "name": name_clean,
                "description": description_clean,
                "image": image_clean,
                "folder": folder,
                "servings": servings_clean,
                "prep_time": prep_time_clean,
                "cook_time": cook_time_clean,
                "ingredients": ingredients_clean,
                "instructions": instructions_clean,
                "source_url": source_url_clean,
                "tags": tags_clean,
            }
            data["recipes"].append(recipe)
            save_data(data)
            # Clear prefill after successful save
            st.session_state.prefill = {}
            st.success(f"✅ '{name_clean}' saved to '{folder}'!")
            st.session_state.page = "browse"
            st.session_state.selected_folder = folder
            st.rerun()


def show_edit_recipe(data: dict) -> None:
    """Form to edit an existing recipe."""
    st.title("✏️ Edit Recipe")

    recipe_idx = st.session_state.get("edit_recipe_index", -1)
    if recipe_idx < 0 or recipe_idx >= len(data["recipes"]):
        st.error("Recipe not found.")
        return

    recipe = data["recipes"][recipe_idx]
    prefill = recipe.copy()

    st.divider()
    st.subheader("Recipe Details")

    with st.form("edit_recipe_form"):
        name = st.text_input("Recipe Name *", value=prefill.get("name", ""))
        description = st.text_area("Description", value=prefill.get("description", ""), height=80)
        image = st.text_input(
            "Image URL or local path",
            value=prefill.get("image", ""),
            placeholder="https://example.com/recipe-image.jpg",
        )
        uploaded_image = st.file_uploader(
            "Or upload a new image file (saved to local images folder)",
            type=["png", "jpg", "jpeg", "gif", "webp"],
            accept_multiple_files=False,
        )

        folder_options = data["folders"] if data["folders"] else ["(no folders – create one first)"]
        default_folder = prefill.get("folder", "")
        default_idx = folder_options.index(default_folder) if default_folder in folder_options else 0
        folder = st.selectbox("Folder *", folder_options, index=default_idx)

        col1, col2, col3 = st.columns(3)
        servings = col1.text_input("Servings", value=prefill.get("servings", ""))
        prep_time = col2.text_input("Prep Time", value=prefill.get("prep_time", ""),
                                    placeholder="e.g. 15 minutes")
        cook_time = col3.text_input("Cook Time", value=prefill.get("cook_time", ""),
                                    placeholder="e.g. 30 minutes")

        ingredients = st.text_area(
            "Ingredients (one per line) *",
            value=prefill.get("ingredients", ""),
            height=150,
            help="Fractions are supported (for example 1/2 cup or 1 1/2 tsp).",
        )
        instructions = st.text_area(
            "Instructions *",
            value=prefill.get("instructions", ""),
            height=200,
        )
        source_url = st.text_input("Source URL (optional)", value=prefill.get("source_url", ""))
        tags_input = st.text_input(
            "Tags (comma-separated) - e.g. soup, crock pot, sheet pan, bowl",
            value=", ".join(prefill.get("tags", [])),
            placeholder="e.g. soup, quick, vegetarian"
        )

        col_save, col_cancel = st.columns(2)
        with col_save:
            submitted = st.form_submit_button("💾 Save Changes", use_container_width=True)
        with col_cancel:
            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)

    if cancelled:
        st.session_state.page = "recipe"
        st.rerun()

    if submitted:
        name_clean = name.strip() if isinstance(name, str) else ""
        description_clean = description.strip() if isinstance(description, str) else ""
        image_clean = image.strip() if isinstance(image, str) else ""
        servings_clean = servings.strip() if isinstance(servings, str) else ""
        prep_time_clean = prep_time.strip() if isinstance(prep_time, str) else ""
        cook_time_clean = cook_time.strip() if isinstance(cook_time, str) else ""
        ingredients_clean = normalize_ingredient_input(ingredients.strip()) if isinstance(ingredients, str) else ""
        instructions_clean = instructions.strip() if isinstance(instructions, str) else ""
        source_url_clean = source_url.strip() if isinstance(source_url, str) else ""
        tags_clean = [tag.strip().lower() for tag in tags_input.split(",") if tag.strip()] if isinstance(tags_input, str) else []

        if uploaded_image is not None:
            try:
                image_clean = save_uploaded_image(uploaded_image)
            except ValueError as exc:
                st.error(str(exc))
                return

        errors = []
        if not name_clean:
            errors.append("Recipe Name is required.")
        if not ingredients_clean:
            errors.append("Ingredients are required.")
        if not instructions_clean:
            errors.append("Instructions are required.")
        if folder == "(no folders – create one first)":
            errors.append("Please create a folder before saving a recipe.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            updated_recipe = {
                "name": name_clean,
                "description": description_clean,
                "image": image_clean,
                "folder": folder,
                "servings": servings_clean,
                "prep_time": prep_time_clean,
                "cook_time": cook_time_clean,
                "ingredients": ingredients_clean,
                "instructions": instructions_clean,
                "source_url": source_url_clean,
                "tags": tags_clean,
            }
            data["recipes"][recipe_idx] = updated_recipe
            save_data(data)
            st.success(f"✅ '{name_clean}' updated!")
            st.session_state.page = "browse"
            st.session_state.selected_folder = folder
            st.session_state.pop("edit_recipe_index", None)
            st.query_params.clear()
            st.query_params["page"] = "browse"
            st.query_params["folder"] = folder
            st.rerun()


def show_add_folder(data: dict) -> None:
    """Form to create a new folder."""
    st.title("📁 Create New Folder")

    with st.form("folder_form"):
        folder_name = st.text_input("Folder Name *", placeholder="e.g. Desserts, Snacks, Lunch…")
        submitted = st.form_submit_button("Create Folder", use_container_width=True)

    if submitted:
        folder_name = folder_name.strip()
        if not folder_name:
            st.error("Folder name cannot be empty.")
        elif folder_name in data["folders"]:
            st.warning(f"A folder named '{folder_name}' already exists.")
        else:
            data["folders"].append(folder_name)
            save_data(data)
            st.success(f"✅ Folder '{folder_name}' created!")
            st.session_state.page = "browse"
            st.session_state.selected_folder = folder_name
            st.rerun()

    if data["folders"]:
        st.divider()
        st.subheader("Existing Folders")
        for folder in data["folders"]:
            count = sum(1 for r in data["recipes"] if r.get("folder") == folder)
            col1, col2 = st.columns([4, 1])
            col1.write(f"📁 **{folder}** – {count} recipe{'s' if count != 1 else ''}")
            if col2.button("Delete", key=f"del_folder_{folder}"):
                # Remove folder and its recipes
                data["folders"].remove(folder)
                data["recipes"] = [r for r in data["recipes"] if r.get("folder") != folder]
                save_data(data)
                st.success(f"Deleted folder '{folder}' and its recipes.")
                st.rerun()


def show_search(data: dict) -> None:
    """Search recipes by title or ingredient."""
    st.title("🔍 Search Recipes")

    search_type = st.radio(
        "Search by:",
        options=["Title", "Ingredient", "Tag"],
        horizontal=True,
    )

    if search_type == "Title":
        placeholder = "e.g. brownies"
    elif search_type == "Ingredient":
        placeholder = "e.g. chocolate"
    else:  # Tag
        placeholder = "e.g. soup, crock pot"
    
    search_query = st.text_input(
        f"Enter {search_type.lower()}...",
        placeholder=placeholder,
    )

    results = []

    if search_query.strip():
        query_lower = search_query.strip().lower()

        if search_type == "Title":
            results = [
                r
                for r in data["recipes"]
                if query_lower in r.get("name", "").lower()
            ]
        elif search_type == "Ingredient":
            for recipe in data["recipes"]:
                ingredients_text = recipe.get("ingredients", "").lower()
                if query_lower in ingredients_text:
                    results.append(recipe)
        else:  # Tag
            query_tags = [tag.strip().lower() for tag in search_query.split(",")]
            for recipe in data["recipes"]:
                recipe_tags = [tag.lower() for tag in recipe.get("tags", [])]
                if any(qtag in recipe_tags for qtag in query_tags):
                    results.append(recipe)

    if search_query.strip():
        st.subheader(f"Results ({len(results)})")

        if not results:
            st.info(f"No recipes found with {search_type.lower()} '{search_query}'.")
        else:
            render_recipe_thumbnail_grid(results, "search_results")
            st.subheader("Recipe Details")

            for i, recipe in enumerate(results):
                folder = recipe.get("folder", "Unknown")
                anchor_id = recipe_anchor_id(recipe, i)
                st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
                with st.container(border=True):
                    top_cols = st.columns([1, 4])

                    with top_cols[0]:
                        if recipe.get("image"):
                            st.image(recipe["image"], width=120)
                        else:
                            st.caption("No image")

                    with top_cols[1]:
                        st.markdown(f"### {recipe['name']}")
                        st.caption(f"📁 {folder}")
                        if recipe.get("tags"):
                            tags_display = ", ".join([f"🏷️ {tag}" for tag in recipe.get("tags", [])])
                            st.caption(tags_display)

                    with st.expander("View recipe details", expanded=False):
                        if recipe.get("image"):
                            st.image(recipe["image"], use_container_width=True)

                        if recipe.get("description"):
                            st.markdown(f"*{recipe['description']}*")

                        meta_cols = st.columns(3)
                        if recipe.get("servings"):
                            meta_cols[0].metric("Servings", recipe["servings"])
                        if recipe.get("prep_time"):
                            meta_cols[1].metric("Prep Time", recipe["prep_time"])
                        if recipe.get("cook_time"):
                            meta_cols[2].metric("Cook Time", recipe["cook_time"])

                        if recipe.get("ingredients"):
                            st.subheader("Ingredients")
                            st.text(format_ingredients_for_display(recipe["ingredients"]))

                        if recipe.get("instructions"):
                            st.subheader("Instructions")
                            st.markdown(format_instructions_for_display(recipe["instructions"]))

                        if recipe.get("source_url"):
                            st.markdown(f"[🔗 Original recipe]({recipe['source_url']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Recipe Book",
        page_icon="📖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize session state
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "selected_folder" not in st.session_state:
        st.session_state.selected_folder = ""
    if "prefill" not in st.session_state:
        st.session_state.prefill = {}

    # Support direct navigation via URL query params.
    # Only let query params drive page state for URL-addressable pages so
    # button-driven flows (like edit_recipe) are not overridden on rerun.
    query_page = get_query_param_value("page")
    query_folder = get_query_param_value("folder")
    url_driven_pages = {"home", "browse", "recipe", "grocery"}
    if st.session_state.page in url_driven_pages and query_page in url_driven_pages:
        st.session_state.page = query_page
    if query_folder:
        st.session_state.selected_folder = query_folder

    data = load_data()

    # ---- Sidebar ----
    with st.sidebar:
        st.title("Trousil Recipe Book")
        st.divider()

        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "home"
            st.query_params.clear()
            st.rerun()
        
        if st.button("🔍 Search", use_container_width=True):
            st.session_state.page = "search"
            st.query_params.clear()
            st.rerun()

        if st.button("➕ Add Recipe", use_container_width=True):
            st.session_state.page = "add_recipe"
            st.session_state.prefill = {}
            st.query_params.clear()
            st.rerun()

        if st.button("📁 Create Folder", use_container_width=True):
            st.session_state.page = "add_folder"
            st.query_params.clear()
            st.rerun()

        if st.button("🛒 Grocery List", use_container_width=True):
            st.session_state.page = "grocery"
            st.query_params.clear()
            st.query_params["page"] = "grocery"
            st.rerun()

        

        if data["folders"]:
            st.divider()
            st.subheader("Folders")
            for folder in data["folders"]:
                count = sum(1 for r in data["recipes"] if r.get("folder") == folder)
                label = f"📁 {folder} ({count})"
                if st.button(label, key=f"sidebar_{folder}", use_container_width=True):
                    st.session_state.page = "browse"
                    st.session_state.selected_folder = folder
                    st.query_params.clear()
                    st.query_params["page"] = "browse"
                    st.query_params["folder"] = folder
                    st.rerun()

    # ---- Main content ----
    page = st.session_state.page

    if page == "home":
        show_home(data)
    elif page == "browse":
        show_browse(data)
    elif page == "recipe":
        show_recipe_detail(data)
    elif page == "edit_recipe":
        show_edit_recipe(data)
    elif page == "add_recipe":
        show_add_recipe(data)
    elif page == "add_folder":
        show_add_folder(data)
    elif page == "grocery":
        show_grocery_list(data)
    elif page == "search":
        show_search(data)


if __name__ == "__main__":
    main()
