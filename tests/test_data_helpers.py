"""Tests for data_helpers.save_uploaded_image."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest

# Patch streamlit before importing data_helpers (it calls st.* at import time)
sys.modules.setdefault("streamlit", MagicMock())
sys.modules.setdefault("streamlit_gsheets", MagicMock())
sys.modules.setdefault("pandas", MagicMock())


def _make_uploaded_file(content: bytes, name: str = "photo.jpg") -> MagicMock:
    """Return a minimal mock that mimics a Streamlit UploadedFile."""
    f = MagicMock()
    f.name = name
    f.getbuffer.return_value = content
    return f


class TestSaveUploadedImage:
    def _call(self, tmp_path: Path, mock_file: MagicMock) -> str:
        import data_helpers

        original = data_helpers.STATIC_DIR
        data_helpers.STATIC_DIR = tmp_path
        try:
            return data_helpers.save_uploaded_image(mock_file)
        finally:
            data_helpers.STATIC_DIR = original

    def test_returns_string_path(self, tmp_path):
        mock_file = _make_uploaded_file(b"fake-image-data", "image.jpg")
        result = self._call(tmp_path, mock_file)
        assert isinstance(result, str)

    def test_file_is_written(self, tmp_path):
        mock_file = _make_uploaded_file(b"img-bytes", "photo.png")
        path = self._call(tmp_path, mock_file)
        # The returned path points to the saved file; verify it exists
        assert Path(path).exists()

    def test_extension_preserved(self, tmp_path):
        mock_file = _make_uploaded_file(b"data", "recipe.webp")
        path = self._call(tmp_path, mock_file)
        assert path.endswith(".webp")

    def test_no_file_raises_value_error(self):
        import data_helpers

        with pytest.raises(ValueError):
            data_helpers.save_uploaded_image(None)

    def test_missing_name_defaults_to_jpg(self, tmp_path):
        class _NoNameFile:
            """File-like object with no .name attribute."""

            def getbuffer(self):
                return b"data"

        path = self._call(tmp_path, _NoNameFile())
        assert path.endswith(".jpg")


class TestRefreshFolders:
    def test_builds_sorted_unique_folder_list(self):
        import data_helpers

        data = {
            "recipes": [
                {"name": "A", "folder": "Dinner"},
                {"name": "B", "folder": "Breakfast"},
                {"name": "C", "folder": "Dinner"},
            ],
            "folders": [],
        }

        data_helpers.refresh_folders(data)

        assert data["folders"] == ["Breakfast", "Dinner"]

    def test_ignores_blank_or_missing_folder_values(self):
        import data_helpers

        data = {
            "recipes": [
                {"name": "A", "folder": ""},
                {"name": "B"},
                {"name": "C", "folder": "Lunch"},
            ],
            "folders": ["Old Folder"],
        }

        data_helpers.refresh_folders(data)

        assert data["folders"] == ["Lunch"]

    def test_sets_empty_folder_list_when_no_recipe_folders_exist(self):
        import data_helpers

        data = {
            "recipes": [{"name": "A", "folder": ""}, {"name": "B"}],
            "folders": ["Dessert"],
        }

        data_helpers.refresh_folders(data)

        assert data["folders"] == []
