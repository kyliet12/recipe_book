import streamlit as st

from formatting_helpers import format_ingredients_for_display, format_instructions_for_display
from ui_helpers import (
    recipe_anchor_id,
    render_recipe_detail_image,
    render_recipe_inline_thumbnail,
    render_recipe_thumbnail_grid,
)


def show_search(data: dict) -> None:
    """Search recipes by title or ingredient."""
    st.title("Search Recipes")

    search_type = st.radio(
        "Search by:",
        options=["Title", "Ingredient", "Tag"],
        horizontal=True,
    )

    if search_type == "Title":
        placeholder = "e.g. brownies"
    elif search_type == "Ingredient":
        placeholder = "e.g. chocolate"
    else:
        placeholder = "e.g. soup, crock pot"

    search_query = st.text_input(
        f"Enter {search_type.lower()}...",
        placeholder=placeholder,
    )

    results: list[dict] = []

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
        else:
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
                        render_recipe_inline_thumbnail(recipe.get("image"))

                    with top_cols[1]:
                        st.markdown(f"### {recipe['name']}")
                        st.caption(f"📁 {folder}")
                        if recipe.get("tags"):
                            tags_display = ", ".join([f"🏷️ {tag}" for tag in recipe.get("tags", [])])
                            st.caption(tags_display)

                    with st.expander("View recipe details", expanded=False):
                        render_recipe_detail_image(recipe.get("image"))

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
