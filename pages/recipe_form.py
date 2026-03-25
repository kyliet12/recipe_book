import streamlit as st

from data_helpers import save_data, save_uploaded_image
from formatting_helpers import normalize_ingredient_input
from scraping_helpers import scrape_recipe_from_image, scrape_recipe_from_url


def _render_recipe_fields(
    *,
    prefill: dict,
    data: dict,
    form_key: str,
    submit_label: str,
    uploader_label: str,
    include_cancel: bool,
) -> tuple[bool, bool, dict]:
    """Render shared recipe form fields and return submission state + raw values."""

    ###
    # Folder
    ###
    folder_options = data["folders"].copy() if data.get("folders") else []
    folder_options.append("➕ Create new folder...")
    
    default_folder = prefill.get("folder", "")
    if default_folder in folder_options:
        default_idx = folder_options.index(default_folder)
    else:
        default_idx = None
        
    selected_dropdown_folder = st.selectbox(
        "Folder *", 
        folder_options, 
        index=default_idx,
        placeholder="Choose a folder...",
        key="folder_selectbox",
    )
    final_folder_name = ""

    if selected_dropdown_folder == "➕ Create new folder...":
        # If they chose to create a new one, get the name from this text box
        new_folder_name = st.text_input(
            "Enter New Folder Name *", 
            placeholder="e.g., Breakfast, Italian, etc.",
            key="new_folder_input"
        )
        final_folder_name = new_folder_name.strip() if isinstance(new_folder_name, str) else ""
    else:
        # Otherwise, use the one from the dropdown (or it's None)
        final_folder_name = selected_dropdown_folder if selected_dropdown_folder else ""

    with st.form(form_key):
        name = st.text_input("Recipe Name *", value=prefill.get("name", ""))
        description = st.text_area("Description", value=prefill.get("description", ""), height=80)
        image = st.text_input(
            "Image URL or local path",
            value=prefill.get("image", ""),
            placeholder="https://example.com/recipe-image.jpg",
        )
        uploaded_image = st.file_uploader(
            uploader_label,
            type=["png", "jpg", "jpeg", "gif", "webp"],
            accept_multiple_files=False,
        )

        col1, col2, col3 = st.columns(3)
        servings = col1.text_input("Servings", value=prefill.get("servings", ""))
        prep_time = col2.text_input("Prep Time", value=prefill.get("prep_time", ""), placeholder="e.g. 15 minutes")
        cook_time = col3.text_input("Cook Time", value=prefill.get("cook_time", ""), placeholder="e.g. 30 minutes")

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
            placeholder="e.g. soup, quick, vegetarian",
        )

        cancelled = False
        if include_cancel:
            col_save, col_cancel = st.columns(2)
            with col_save:
                submitted = st.form_submit_button(submit_label, width="stretch")
            with col_cancel:
                cancelled = st.form_submit_button("❌ Cancel", width="stretch")
        else:
            submitted = st.form_submit_button(submit_label, width="stretch")

    values = {
        "name": name,
        "description": description,
        "image": image,
        "uploaded_image": uploaded_image,
        "folder": final_folder_name,
        "servings": servings,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "ingredients": ingredients,
        "instructions": instructions,
        "source_url": source_url,
        "tags_input": tags_input,
    }
    return submitted, cancelled, values


def _prepare_recipe_payload(values: dict, *, folder_error_message: str) -> tuple[dict | None, list[str]]:
    """Normalize and validate form values, returning payload + list of validation errors."""
    name_clean = values["name"].strip() if isinstance(values["name"], str) else ""
    description_clean = values["description"].strip() if isinstance(values["description"], str) else ""
    image_clean = values["image"].strip() if isinstance(values["image"], str) else ""
    servings_clean = values["servings"].strip() if isinstance(values["servings"], str) else ""
    prep_time_clean = values["prep_time"].strip() if isinstance(values["prep_time"], str) else ""
    cook_time_clean = values["cook_time"].strip() if isinstance(values["cook_time"], str) else ""
    ingredients_clean = normalize_ingredient_input(values["ingredients"].strip()) if isinstance(values["ingredients"], str) else ""
    instructions_clean = values["instructions"].strip() if isinstance(values["instructions"], str) else ""
    source_url_clean = values["source_url"].strip() if isinstance(values["source_url"], str) else ""
    tags_clean = [tag.strip().lower() for tag in values["tags_input"].split(",") if tag.strip()] if isinstance(values["tags_input"], str) else []

    uploaded_image = values.get("uploaded_image")
    if uploaded_image is not None:
        try:
            image_clean = save_uploaded_image(uploaded_image)
        except ValueError as exc:
            return None, [str(exc)]

    errors = []
    if not name_clean:
        errors.append("Recipe Name is required.")
    if not ingredients_clean:
        errors.append("Ingredients are required.")
    if not instructions_clean:
        errors.append("Instructions are required.")
    if values["folder"] == "(no folders – create one first)":
        errors.append(folder_error_message)

    payload = {
        "name": name_clean,
        "description": description_clean,
        "image": image_clean,
        "folder": values["folder"],
        "servings": servings_clean,
        "prep_time": prep_time_clean,
        "cook_time": cook_time_clean,
        "ingredients": ingredients_clean,
        "instructions": instructions_clean,
        "source_url": source_url_clean,
        "tags": tags_clean,
    }
    return payload, errors


def show_add_recipe(data: dict) -> None:
    """Form to add a new recipe (manual or via URL)."""
    st.title("➕ Add New Recipe")

    method = st.radio(
        "How would you like to add the recipe?",
        ["Enter details manually", "Import from a website URL", "Import from an image"],
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
    elif method == "Import from an image":
        recipe_image = st.file_uploader(
            "Recipe image",
            type=["png", "jpg", "jpeg", "gif", "webp"],
            accept_multiple_files=False,
            key="recipe_import_image",
            help="Upload a photo or screenshot of a recipe card/page.",
        )

        if st.button("Extract From Image"):
            if recipe_image is None:
                st.error("Please upload an image first.")
            else:
                with st.spinner("Reading the image and extracting recipe details…"):
                    try:
                        prefill = scrape_recipe_from_image(bytes(recipe_image.getbuffer()))

                        # Default to using the imported recipe photo as the recipe image.
                        try:
                            prefill["image"] = save_uploaded_image(recipe_image)
                        except ValueError:
                            # The OCR parse can still be useful even if image saving fails.
                            pass

                        st.success("Recipe details extracted from image. Review and save below.")
                        st.session_state.prefill = prefill
                    except ValueError as exc:
                        st.error(f"⚠️ {exc}")
                        st.session_state.prefill = {}
        prefill = st.session_state.get("prefill", {})

    st.divider()
    st.subheader("Recipe Details")

    submitted, _, values = _render_recipe_fields(
        prefill=prefill,
        data=data,
        form_key="recipe_form",
        submit_label="💾 Save Recipe",
        uploader_label="Or upload an image file (saved to local images folder)",
        include_cancel=False,
    )

    if submitted:
        recipe, errors = _prepare_recipe_payload(
            values,
            folder_error_message="Please create a folder before adding a recipe.",
        )

        if errors:
            for err in errors:
                st.error(err)
        else:
            assert recipe is not None
            data["recipes"].append(recipe)
            save_data(data)
            st.session_state.prefill = {}
            st.success(f"✅ '{recipe['name']}' saved to '{recipe['folder']}'!")
            st.session_state.page = "browse"
            st.session_state.selected_folder = recipe["folder"]
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

    submitted, cancelled, values = _render_recipe_fields(
        prefill=prefill,
        data=data,
        form_key="edit_recipe_form",
        submit_label="💾 Save Changes",
        uploader_label="Or upload a new image file (saved to local images folder)",
        include_cancel=True,
    )

    if cancelled:
        st.session_state.page = "recipe"
        st.rerun()

    if submitted:
        updated_recipe, errors = _prepare_recipe_payload(
            values,
            folder_error_message="Please create a folder before saving a recipe.",
        )

        if errors:
            for err in errors:
                st.error(err)
        else:
            assert updated_recipe is not None
            data["recipes"][recipe_idx] = updated_recipe
            save_data(data)
            st.success(f"✅ '{updated_recipe['name']}' updated!")
            st.session_state.page = "browse"
            st.session_state.selected_folder = updated_recipe["folder"]
            st.session_state.pop("edit_recipe_index", None)
            st.query_params.clear()
            st.query_params["page"] = "browse"
            st.query_params["folder"] = updated_recipe["folder"]
            st.rerun()
