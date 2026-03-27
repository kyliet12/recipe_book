import streamlit as st


def show_home(data: dict) -> None:
    """Landing page - list all folders and a summary of recipes in each."""
    st.title("Our Recipe Book")
    st.write("Welcome! Use the sidebar to navigate the website. You can add new recipes, search recipes, or create a grocery list.")
    if not data["folders"]:
        st.info("No recipes yet. Start by adding a recipe using the sidebar!")
        return

    cols = st.columns(3)
    for idx, folder in enumerate(data["folders"]):
        count = data.get("folder_counts", {}).get(folder, 0)
        with cols[idx % 3]:
            if st.button(
                f"📁 {folder}\n\n*{count} recipe{'s' if count != 1 else ''}*",
                key=f"home_folder_{folder}",
                width="stretch",
            ):
                st.session_state.page = "browse"
                st.session_state.selected_folder = folder
                st.rerun()
