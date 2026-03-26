import time
from urllib.parse import urlparse
from io import BytesIO
import os
from PIL import Image
import json
import html

import streamlit as st
from google import genai
import requests

from formatting_helpers import clean_time_string

def scrape_recipe_from_image(image_file: bytes) -> dict:
    """Extract recipe details and smart tags from an image using the Gemini API."""
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key not found. Please add GEMINI_API_KEY to your Streamlit secrets.")

    client = genai.Client(api_key=api_key)

    try:
        img = Image.open(BytesIO(image_file))
    except Exception as exc:
        raise ValueError(f"Could not read the uploaded image: {exc}")

    # UPDATED PROMPT: Added 'notes'
    prompt = """
    You are a helpful culinary assistant. Please look at this recipe image and extract the information into a structured JSON format. 
    Return ONLY a raw JSON object and absolutely no markdown formatting or backticks. 
    Use the exact following keys: 
    'name', 'description', 'servings', 'prep_time', 'cook_time', 'ingredients', 'instructions', 'notes', 'tags'. 

    CRITICAL TAGGING INSTRUCTIONS for the 'tags' key:
    Read the instructions carefully to identify the cooking method and equipment. You MUST include tags for things like "sheet pan", "air fryer", "crock pot", "slow cooker", "instant pot", "one pot", or "grill" if they apply.  Also include general categories (e.g., "vegan", "dessert"). Do not include ingredients. Provide a JSON array of 2 to 4 lowercase strings.
    
    For 'ingredients', format it as a single string with each ingredient separated by a newline (\\n). 
    For 'instructions', format it as a single string with numbered steps. 
    For 'notes', extract any baker's tips, storage instructions, or substitutions. If none exist, leave it blank.
    If any information is missing from the image, leave the value as an empty string ("").
    """

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, img]
            )
            
            text_response = response.text.strip()
            text_response = text_response.replace("```json", "").replace("```", "").strip()
            recipe_data = json.loads(text_response)
            
            # UPDATED KEYS: Added 'notes'
            expected_keys = ["name", "description", "servings", "prep_time", "cook_time", "ingredients", "instructions", "notes", "tags"]
            for key in expected_keys:
                if key not in recipe_data:
                    recipe_data[key] = [] if key == "tags" else ""
            
            recipe_data["prep_time"] = clean_time_string(recipe_data.get("prep_time", ""))
            recipe_data["cook_time"] = clean_time_string(recipe_data.get("cook_time", ""))
                    
            return recipe_data

        except Exception as exc:
            error_msg = str(exc)
            if "503" in error_msg or "UNAVAILABLE" in error_msg:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"Server busy. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
                else:
                    raise ValueError("The AI model is experiencing high traffic. Please wait a minute and try again.")
            else:
                raise ValueError(f"Failed to extract recipe using the AI model: {exc}")


def scrape_recipe_from_url(url: str) -> dict:
    """Fetch a webpage and use Gemini to extract the recipe and smart tags."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http:// and https:// URLs are supported.")
    if not parsed.netloc:
        raise ValueError("Invalid URL - no hostname found.")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"Failed to fetch the URL: {exc}")

    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key not found.")

    client = genai.Client(api_key=api_key)
    html_content = html.unescape(response.text[:100000])

    prompt = f"""
    You are a helpful culinary assistant. I am providing you with the raw HTML/text of a food blog webpage.
    Find the actual recipe hidden in this text and extract it into a structured JSON format.
    Return ONLY a raw JSON object and absolutely no markdown formatting or backticks. 
    Use the exact following keys: 
    'name', 'description', 'image', 'servings', 'prep_time', 'cook_time', 'ingredients', 'instructions', 'notes', 'tags'. 

    CRITICAL INSTRUCTIONS:
    - For 'tags': Read the instructions carefully to identify the cooking method and equipment (e.g., "sheet pan", "air fryer", "slow cooker"). Also include general categories (e.g., "vegan", "dessert"). Do not include ingredients. Provide a JSON array of 2 to 4 lowercase strings.
    - For 'image': Extract the URL of the main recipe photo. Look for standard image extensions (.jpg, .png).
    - For 'ingredients': Format as a single string with each ingredient separated by a newline (\\n). 
    - For 'instructions': Format as a single string with numbered steps separated by a newline (\\n). 
    - For 'notes': Extract any recipe tips, storage instructions, or substitutions.
    If any information is missing, leave the value as an empty string ("").

    WEBPAGE CONTENT:
    {html_content}
    """

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        try:
            ai_response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            text_response = ai_response.text.strip()
            text_response = text_response.replace("```json", "").replace("```", "").strip()
            recipe_data = json.loads(text_response)
            
            # UPDATED KEYS: Added 'notes'
            expected_keys = ["name", "description", "image", "servings", "prep_time", "cook_time", "ingredients", "instructions", "notes", "tags"]
            for key in expected_keys:
                if key not in recipe_data:
                    recipe_data[key] = [] if key == "tags" else ""
            
            recipe_data["prep_time"] = clean_time_string(recipe_data.get("prep_time", ""))
            recipe_data["cook_time"] = clean_time_string(recipe_data.get("cook_time", ""))
            recipe_data["source_url"] = url
            recipe_data["folder"] = ""
            
            return recipe_data

        except Exception as exc:
            error_msg = str(exc)
            if "503" in error_msg or "UNAVAILABLE" in error_msg:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"Server busy. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
                else:
                    raise ValueError("The AI model is experiencing high traffic. Please wait a minute and try again.")
            else:
                raise ValueError(f"Failed to extract recipe using the AI model: {exc}")