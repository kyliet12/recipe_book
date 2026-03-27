from pathlib import Path
import cloudinary
import cloudinary.uploader
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection


STATIC_DIR = Path("static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NfkTKNIVhoKA9VhxyO8RjjtARfSSP3aC56QMAgOrNYc/edit"

@st.cache_data(ttl=3600)  # Cache for 1 hour to reduce load on Google Sheets
def load_data() -> dict:
    """Fetch data from Google Sheets and convert to our dictionary format."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # Respect cache_data decorator by using the default ttl instead of ttl=0
        df = conn.read(spreadsheet=SHEET_URL, worksheet="recipes")
        df = df.fillna("")  # Clean up empty cells
        
        recipes = df.to_dict(orient="records")
        
        # Clean up tags (Sheets stores lists as strings like "['soup', 'quick']")
        for r in recipes:
            if isinstance(r.get("tags"), str) and r["tags"]:
                r["tags"] = [t.strip(" '\"[]") for t in r["tags"].split(",") if t.strip(" '\"[]")]
            else:
                r["tags"] = []
                
        # Dynamically build the folder list and recipe counts based on existing recipes
        folders = sorted(set(r.get("folder", "") for r in recipes if r.get("folder")))
        folder_counts = {folder: sum(1 for r in recipes if r.get("folder") == folder) for folder in folders}
        
        # Create a recipe ID map for O(1) lookups instead of O(n) index() calls
        recipe_id_map = {id(recipe): i for i, recipe in enumerate(recipes)}
        
        return {"recipes": recipes, "folders": folders, "folder_counts": folder_counts, "recipe_id_map": recipe_id_map}
        
    except Exception as e:
        # If the sheet is empty or fails, return an empty structure safely
        print(f"Error loading sheet: {e}")
        return {"recipes": [], "folders": []}

def save_data(data: dict) -> None:
    """Convert the recipe dictionary to a DataFrame and push to Google Sheets."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Convert tag lists to strings so Pandas can push them to Sheets safely
    recipes_to_save = []
    for r in data["recipes"]:
        r_copy = r.copy()
        r_copy["tags"] = str(r_copy.get("tags", []))
        recipes_to_save.append(r_copy)
        
    df = pd.DataFrame(recipes_to_save)
    
    # Update overwrites the sheet with the new dataframe
    conn.update(spreadsheet=SHEET_URL, worksheet="recipes", data=df)
    st.cache_data.clear()  # Clear cache so next load refreshes from Sheets
    data["folders"] = sorted({r.get("folder", "") for r in data.get("recipes", []) if r.get("folder")})
    data["folder_counts"] = {folder: sum(1 for r in data["recipes"] if r.get("folder") == folder) for folder in data["folders"]}
    # Rebuild recipe_id_map after changes
    data["recipe_id_map"] = {id(recipe): i for i, recipe in enumerate(data["recipes"])}

def refresh_folders(data: dict) -> None:
    """Keep the in-memory folder list in sync with current recipes."""
    data["folders"] = sorted({r.get("folder", "") for r in data.get("recipes", []) if r.get("folder")})

def save_uploaded_image(uploaded_file) -> str:
    """
    Uploads an image file to Cloudinary and returns the permanent public URL.
    """
    try:
        # 1. Authenticate with your secrets
        cloudinary.config(
            cloud_name = st.secrets["cloudinary"]["cloud_name"],
            api_key = st.secrets["cloudinary"]["api_key"],
            api_secret = st.secrets["cloudinary"]["api_secret"],
            secure = True
        )
        
        # 2. Upload the file bytes directly to Cloudinary
        # We use .getvalue() to get the raw bytes from the Streamlit file uploader
        upload_result = cloudinary.uploader.upload(uploaded_file.getvalue())
        
        # 3. Return the secure HTTPS link provided by Cloudinary
        return upload_result["secure_url"]
        
    except Exception as e:
        raise ValueError(f"Failed to upload image to Cloudinary: {e}")