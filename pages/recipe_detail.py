import streamlit as st

from data_helpers import save_data
from formatting_helpers import format_ingredients_for_display, format_instructions_for_display
from ui_helpers import get_query_param_value, recipe_anchor_id


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
        st.image(selected_recipe["image"], width="stretch")

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
        if st.button("✏️ Edit recipe", key=f"edit_single_{folder}_{selected_idx}", width="stretch"):
            global_idx = data["recipes"].index(selected_recipe)
            st.session_state.edit_recipe_index = global_idx
            st.session_state.page = "edit_recipe"
            st.rerun()

    with action_cols[1]:
        if st.button("🗑️ Delete recipe", key=f"delete_single_{folder}_{selected_idx}", width="stretch"):
            global_idx = data["recipes"].index(selected_recipe)
            data["recipes"].pop(global_idx)
            save_data(data)
            st.success("Recipe deleted.")
            st.query_params.clear()
            st.query_params["page"] = "browse"
            st.query_params["folder"] = folder
            st.rerun()
