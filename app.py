import json
import os
from urllib.parse import urlparse

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

    def safe_get(fn, default=""):
        try:
            val = fn()
            return val if val else default
        except (ElementNotFoundInHtml, FieldNotProvidedByWebsiteException, Exception):
            return default

    ingredients = safe_get(scraper.ingredients, [])
    if isinstance(ingredients, list):
        ingredients = "\n".join(ingredients)

    instructions = safe_get(scraper.instructions, "")

    return {
        "name": safe_get(scraper.title, ""),
        "description": "",
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
    st.title("📖 My Recipe Book")
    st.write("Welcome! Use the sidebar to browse folders or add new recipes and folders.")

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
    st.title(f"📁 {folder}")

    folder_recipes = [r for r in data["recipes"] if r.get("folder") == folder]

    if not folder_recipes:
        st.info(f"No recipes in '{folder}' yet. Add one using the sidebar!")
        return

    for i, recipe in enumerate(folder_recipes):
        with st.expander(f"🍽️ {recipe['name']}", expanded=False):
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
                st.text(recipe["ingredients"])

            if recipe.get("instructions"):
                st.subheader("Instructions")
                st.markdown(recipe["instructions"])

            if recipe.get("source_url"):
                st.markdown(f"[🔗 Original recipe]({recipe['source_url']})")

            # Delete button
            if st.button("🗑️ Delete recipe", key=f"delete_{folder}_{i}"):
                global_idx = data["recipes"].index(recipe)
                data["recipes"].pop(global_idx)
                save_data(data)
                st.success(f"Deleted '{recipe['name']}'.")
                st.rerun()


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
        )
        instructions = st.text_area(
            "Instructions *",
            value=prefill.get("instructions", ""),
            height=200,
        )
        source_url = st.text_input("Source URL (optional)", value=prefill.get("source_url", ""))

        submitted = st.form_submit_button("💾 Save Recipe", use_container_width=True)

    if submitted:
        errors = []
        if not name.strip():
            errors.append("Recipe Name is required.")
        if not ingredients.strip():
            errors.append("Ingredients are required.")
        if not instructions.strip():
            errors.append("Instructions are required.")
        if folder == "(no folders – create one first)":
            errors.append("Please create a folder before adding a recipe.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            recipe = {
                "name": name.strip(),
                "description": description.strip(),
                "folder": folder,
                "servings": servings.strip(),
                "prep_time": prep_time.strip(),
                "cook_time": cook_time.strip(),
                "ingredients": ingredients.strip(),
                "instructions": instructions.strip(),
                "source_url": source_url.strip(),
            }
            data["recipes"].append(recipe)
            save_data(data)
            # Clear prefill after successful save
            st.session_state.prefill = {}
            st.success(f"✅ '{name}' saved to '{folder}'!")
            st.session_state.page = "browse"
            st.session_state.selected_folder = folder
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

    data = load_data()

    # ---- Sidebar ----
    with st.sidebar:
        st.title("📖 Recipe Book")
        st.divider()

        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()

        if st.button("➕ Add Recipe", use_container_width=True):
            st.session_state.page = "add_recipe"
            st.session_state.prefill = {}
            st.rerun()

        if st.button("📁 Create Folder", use_container_width=True):
            st.session_state.page = "add_folder"
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
                    st.rerun()

    # ---- Main content ----
    page = st.session_state.page

    if page == "home":
        show_home(data)
    elif page == "browse":
        show_browse(data)
    elif page == "add_recipe":
        show_add_recipe(data)
    elif page == "add_folder":
        show_add_folder(data)


if __name__ == "__main__":
    main()
