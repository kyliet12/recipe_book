import streamlit as st

from data_helpers import refresh_folders, save_data
from formatting_helpers import format_ingredients_for_display, format_instructions_for_display
from ui_helpers import recipe_anchor_id, render_recipe_thumbnail_grid


def show_browse(data: dict) -> None:
    """Browse recipes in the currently selected folder."""
    folder = st.session_state.get("selected_folder", "")
    st.title(f"{folder}")

    nav_cols = st.columns(2)
    with nav_cols[0]:
        if st.button("← Back to Home", key="back_to_home"):
            st.session_state.page = "home"
            st.session_state.pop("selected_folder", None)
            st.query_params.clear()
            st.rerun()

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
                    st.image(recipe["image"], width="stretch")

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
                    if st.button("✏️ Edit recipe", key=f"edit_{folder}_{i}", width="stretch"):
                        global_idx = data["recipes"].index(recipe)
                        st.session_state.edit_recipe_index = global_idx
                        st.session_state.page = "edit_recipe"
                        st.rerun()

                with action_cols[1]:
                    if st.button("🗑️ Delete recipe", key=f"delete_{folder}_{i}", width="stretch"):
                        global_idx = data["recipes"].index(recipe)
                        data["recipes"].pop(global_idx)
                        refresh_folders(data)
                        save_data(data)
                        st.success(f"Deleted '{recipe['name']}'.")
                        st.rerun()
