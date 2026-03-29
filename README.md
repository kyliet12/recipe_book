# Recipe Book

Recipe Book is a Streamlit app for collecting, organizing, searching, and cooking from our family recipes.
It stores recipes in Google Sheets, supports AI-assisted import from URLs or photos, and can generate a combined grocery list from selected recipes.

*Created using AI agents*

## What this app does

- Organizes recipes into folders (for example Breakfast, Dinner, Desserts).
- Lets you add and edit recipes manually.
- Imports recipes from web pages.
- Extracts recipes from one or more uploaded images using Gemini.
- Searches by title, ingredient, or tags.
- Builds an interactive grocery list that combines matching ingredients.
- Exports grocery lists as a plain text file.

## Project structure

- `app.py`: Main Streamlit entry point and page routing.
- `pages/`: UI pages (home, browse, search, grocery, recipe form, recipe detail).
- `data_helpers.py`: Google Sheets load/save, folder sync, and image upload helpers.
- `scraping_helpers.py`: URL scraping and Gemini extraction logic.
- `grocery_helpers.py`: Ingredient parsing and grocery list aggregation.
- `formatting_helpers.py`: Recipe text formatting and ingredient normalization.
- `ui_helpers.py`: Shared UI rendering helpers.
- `tests/`: Pytest test suite for helper and form logic.

## Requirements

- Python 3.10+ (3.11 recommended)
- A Google Sheet for recipe storage
- Streamlit secrets configured for:
	- Google Sheets connection
	- Gemini API key
	- Cloudinary credentials (optional but recommended for image hosting)

## Quick start

1. Clone the repository and move into the project folder.
2. Create and activate a virtual environment.
3. Install dependencies.
4. Add your Streamlit secrets.
5. Run the Streamlit app.

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure Streamlit secrets

Create or edit `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_gemini_key"

[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/your_sheet_id/edit"
type = "service_account"
project_id = "your_project_id"
private_key_id = "your_private_key_id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your_service_account@your_project.iam.gserviceaccount.com"
client_id = "your_client_id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"

[cloudinary]
cloud_name = "your_cloud_name"
api_key = "your_cloudinary_api_key"
api_secret = "your_cloudinary_api_secret"
```

### Run the app

```bash
streamlit run app.py
```

## How to use

- Home: Browse folders and jump into recipe collections.
- Add Recipe:
	- Enter details manually.
	- Import from URL.
	- Import from one or more images.
- Browse: View recipe cards, expand details, edit, and delete.
- Search: Find recipes by title, ingredient, or tag.
- Grocery List: Select recipes, generate a grouped list, check items off, and download.

## Data model (high level)

Each recipe includes fields such as:

- `name`
- `description`
- `image`
- `folder`
- `servings`
- `prep_time`
- `cook_time`
- `ingredients`
- `instructions`
- `notes`
- `source_url`
- `tags`

## Troubleshooting

- App shows no recipes:
	- Verify Google Sheets credentials and spreadsheet URL in `.streamlit/secrets.toml`.
- URL import fails:
	- Some websites block scraping; the app will attempt AI fallback.
- Image import fails:
	- Confirm `GEMINI_API_KEY` is valid and has quota.
- Missing or broken images:
	- Verify Cloudinary credentials and image URLs.

## Tech stack

- Streamlit
- Pandas
- streamlit-gsheets-connection
- recipe-scrapers
- Google GenAI SDK
- Cloudinary
- Pillow
