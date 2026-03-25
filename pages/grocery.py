import streamlit as st

from grocery_helpers import build_grocery_list


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
            width="stretch",
        )
