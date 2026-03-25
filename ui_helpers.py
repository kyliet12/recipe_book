import html
import re
from urllib.parse import urlencode

import streamlit as st


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
        image_path_or_url = str(recipe.get("image", "")).strip()
        query = urlencode({"page": "recipe", "folder": folder, "recipe": anchor})

        thumb = "<div class='recipe-thumb-placeholder'>No image</div>"

        if image_path_or_url:
            # If it's an external web URL, use it directly
            if image_path_or_url.startswith(("http://", "https://")):
                img_src = html.escape(image_path_or_url)
                thumb = f"<img src=\"{img_src}\" alt=\"{title}\" />"
            
            # If it's a local file in our static folder
            elif image_path_or_url.startswith("static/"):
                # Streamlit serves files from the 'static' folder at the '/app/static/' URL path
                # We strip the "static/" prefix from the local path to avoid duplication
                filename = image_path_or_url.replace("static/", "", 1)
                img_src = f"/app/static/{filename}"
                thumb = f"<img src=\"{img_src}\" alt=\"{title}\" />"

        cards.append(
            (
                f"<a class='recipe-card' href='?{query}' target='_self'>"
                f"{thumb}"
                f"<div class='recipe-card-title'>{title}</div>"
                "</a>"
            )
        )

    st.markdown(f"<div class='recipe-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)
