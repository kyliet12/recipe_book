import streamlit as st


def render_sidebar(data: dict) -> None:
    """Render the app sidebar and handle navigation actions."""
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

        if st.button("🛒 Grocery List", use_container_width=True):
            st.session_state.page = "grocery"
            st.query_params.clear()
            st.query_params["page"] = "grocery"
            st.rerun()

        if data["folders"]:
            st.divider()
            st.subheader("Folders")
            for folder in data["folders"]:
                count = data.get("folder_counts", {}).get(folder, 0)
                label = f"📁 {folder} ({count})"
                if st.button(label, key=f"sidebar_{folder}", use_container_width=True):
                    st.session_state.page = "browse"
                    st.session_state.selected_folder = folder
                    st.query_params.clear()
                    st.query_params["page"] = "browse"
                    st.query_params["folder"] = folder
                    st.rerun()
