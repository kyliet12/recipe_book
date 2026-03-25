import streamlit as st

from data_helpers import load_data
from pages.browse import show_browse
from pages.grocery import show_grocery_list
from pages.home import show_home
from pages.recipe_detail import show_recipe_detail
from pages.recipe_form import show_add_recipe, show_edit_recipe
from pages.search import show_search
from sidebar import render_sidebar
from ui_helpers import get_query_param_value


def main() -> None:
    st.set_page_config(
        page_title="Recipe Book",
        page_icon="📖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "selected_folder" not in st.session_state:
        st.session_state.selected_folder = ""
    if "prefill" not in st.session_state:
        st.session_state.prefill = {}

    query_page = get_query_param_value("page")
    query_folder = get_query_param_value("folder")
    url_driven_pages = {"home", "browse", "recipe", "grocery"}
    if st.session_state.page in url_driven_pages and query_page in url_driven_pages:
        st.session_state.page = query_page
    if query_folder:
        st.session_state.selected_folder = query_folder

    data = load_data()

    render_sidebar(data)

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
    elif page == "grocery":
        show_grocery_list(data)
    elif page == "search":
        show_search(data)


if __name__ == "__main__":
    main()
