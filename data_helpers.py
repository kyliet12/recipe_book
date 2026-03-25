from pathlib import Path
from typing import Any
import uuid

import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import uuid
from pathlib import Path


STATIC_DIR = Path("static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1NfkTKNIVhoKA9VhxyO8RjjtARfSSP3aC56QMAgOrNYc/edit"
ttl_secrets = st.secrets["connections"]["gsheets"]

def load_data() -> dict:
    """Fetch data from Google Sheets and convert to our dictionary format."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        # ttl=0 ensures we fetch fresh data instead of using a cached version
        df = conn.read(spreadsheet=SHEET_URL, worksheet="recipes", ttl=0)
        df = df.fillna("")  # Clean up empty cells
        
        recipes = df.to_dict(orient="records")
        
        # Clean up tags (Sheets stores lists as strings like "['soup', 'quick']")
        for r in recipes:
            if isinstance(r.get("tags"), str) and r["tags"]:
                r["tags"] = [t.strip(" '\"[]") for t in r["tags"].split(",") if t.strip(" '\"[]")]
            else:
                r["tags"] = []
                
        # Dynamically build the folder list based on existing recipes
        folders = list(set(r.get("folder", "") for r in recipes if r.get("folder")))
        
        return {"recipes": recipes, "folders": folders}
        
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
    st.cache_data.clear() # Force clear the cache so the next load is completely fresh

def save_uploaded_image(uploaded_file: Any) -> str:
    """
    Saves an uploaded image (from st.file_uploader or Gemini API) 
    to the static folder and returns the relative file path.
    """
    if uploaded_file is None:
        raise ValueError("No image provided.")

    # Generate a unique ID for the filename
    file_id = uuid.uuid4().hex[:8]
    
    # Try to keep the original extension, default to .jpg
    try:
        ext = uploaded_file.name.split(".")[-1].lower()
    except AttributeError:
        ext = "jpg"
        
    filename = f"{file_id}.{ext}"
    filepath = STATIC_DIR / filename
    
    # Write the bytes to the static folder
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    # Return the path as a string (e.g., "static/a1b2c3d4.jpg")
    # Native st.image() can read this directly from the local disk
    return str(filepath.as_posix())