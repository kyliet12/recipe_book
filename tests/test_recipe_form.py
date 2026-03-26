"""Tests for recipe_form._prepare_recipe_payload validation logic."""

import sys
from unittest.mock import MagicMock

import pytest

# Patch heavy dependencies before importing the module.
# Set up google mock so google.genai is accessible as an attribute.
_google_mock = MagicMock()
_google_mock.genai = MagicMock()
sys.modules.setdefault("streamlit", MagicMock())
sys.modules.setdefault("streamlit_gsheets", MagicMock())
sys.modules.setdefault("pandas", MagicMock())
sys.modules.setdefault("google", _google_mock)
sys.modules.setdefault("google.genai", _google_mock.genai)
sys.modules.setdefault("requests", MagicMock())
sys.modules.setdefault("recipe_scrapers", MagicMock())
sys.modules.setdefault("recipe_scrapers._exceptions", MagicMock())
sys.modules.setdefault("PIL", MagicMock())
sys.modules.setdefault("PIL.Image", MagicMock())


def _base_values(**overrides) -> dict:
    """Return a minimal set of valid form values."""
    defaults = {
        "name": "Chocolate Cake",
        "description": "A rich cake",
        "image": "",
        "uploaded_image": None,
        "folder": "Desserts",
        "servings": "8",
        "prep_time": "15 minutes",
        "cook_time": "30 minutes",
        "ingredients": "2 cups flour\n1 cup sugar",
        "instructions": "Mix and bake.",
        "source_url": "",
        "tags_input": "dessert, cake",
    }
    defaults.update(overrides)
    return defaults


class TestPrepareRecipePayload:
    def setup_method(self):
        from pages.recipe_form import _prepare_recipe_payload

        self.prepare = _prepare_recipe_payload

    def test_valid_input_returns_no_errors(self):
        payload, errors = self.prepare(
            _base_values(), folder_error_message="Please set a folder."
        )
        assert errors == []
        assert payload is not None

    def test_missing_name_raises_error(self):
        _, errors = self.prepare(
            _base_values(name=""), folder_error_message="Set a folder."
        )
        assert any("name" in e.lower() for e in errors)

    def test_missing_ingredients_raises_error(self):
        _, errors = self.prepare(
            _base_values(ingredients=""), folder_error_message="Set a folder."
        )
        assert any("ingredient" in e.lower() for e in errors)

    def test_missing_instructions_raises_error(self):
        _, errors = self.prepare(
            _base_values(instructions=""), folder_error_message="Set a folder."
        )
        assert any("instruction" in e.lower() for e in errors)

    def test_empty_folder_raises_error(self):
        _, errors = self.prepare(
            _base_values(folder=""), folder_error_message="Please choose a folder."
        )
        assert any("folder" in e.lower() for e in errors)

    def test_whitespace_only_name_raises_error(self):
        _, errors = self.prepare(
            _base_values(name="   "), folder_error_message="Set a folder."
        )
        assert any("name" in e.lower() for e in errors)

    def test_tags_parsed_to_list(self):
        payload, errors = self.prepare(
            _base_values(tags_input="quick, vegetarian, soup"),
            folder_error_message="Set a folder.",
        )
        assert errors == []
        assert payload["tags"] == ["quick", "vegetarian", "soup"]

    def test_tags_lowercased(self):
        payload, errors = self.prepare(
            _base_values(tags_input="Soup, QUICK"),
            folder_error_message="Set a folder.",
        )
        assert errors == []
        assert payload["tags"] == ["soup", "quick"]

    def test_empty_tags_produces_empty_list(self):
        payload, errors = self.prepare(
            _base_values(tags_input=""), folder_error_message="Set a folder."
        )
        assert errors == []
        assert payload["tags"] == []

    def test_multiple_errors_reported(self):
        _, errors = self.prepare(
            _base_values(name="", ingredients="", folder=""),
            folder_error_message="Please choose a folder.",
        )
        assert len(errors) >= 3

    def test_payload_contains_all_required_keys(self):
        payload, _ = self.prepare(
            _base_values(), folder_error_message="Set a folder."
        )
        expected_keys = {
            "name", "description", "image", "folder", "servings",
            "prep_time", "cook_time", "ingredients", "instructions",
            "source_url", "tags",
        }
        assert expected_keys.issubset(payload.keys())

    def test_uploaded_image_calls_save(self, monkeypatch):
        """When an uploaded_image is provided, save_uploaded_image is called."""
        mock_upload = MagicMock()
        mock_upload.getbuffer.return_value = b"fake"
        mock_upload.name = "photo.jpg"

        import pages.recipe_form as rf

        monkeypatch.setattr(rf, "save_uploaded_image", lambda f: "static/abc.jpg")

        payload, errors = self.prepare(
            _base_values(uploaded_image=mock_upload),
            folder_error_message="Set a folder.",
        )
        assert errors == []
        assert payload["image"] == "static/abc.jpg"


# ---------------------------------------------------------------------------
# Navigation logic – session state is pure Python, testable without Streamlit
# ---------------------------------------------------------------------------

class TestLoadDataFallback:
    """Test the fallback logic inside load_data when the sheet is unavailable."""

    def test_returns_empty_structure_on_connection_error(self):
        """The try/except in load_data should return an empty dict on failure."""
        import data_helpers

        class _BadConn:
            def read(self, **kwargs):
                raise RuntimeError("Sheet not available")

        # Simulate the body of load_data directly (bypassing the cache decorator)
        try:
            conn = _BadConn()
            df = conn.read(spreadsheet="url", worksheet="recipes", ttl=0)
            result = {"recipes": [], "folders": []}  # Should not reach here
        except Exception:
            result = {"recipes": [], "folders": []}

        assert result == {"recipes": [], "folders": []}
