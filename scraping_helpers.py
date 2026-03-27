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
from recipe_scrapers import scrape_html

from formatting_helpers import clean_time_string

def scrape_recipes_from_images(image_files: list[bytes], combine: bool) -> list[dict]:
    """Extract recipe(s) from a list of images using the Gemini API."""
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key not found. Please add GEMINI_API_KEY to your Streamlit secrets.")

    client = genai.Client(api_key=api_key)

    try:
        # Load all images into a list of PIL Images
        imgs = [Image.open(BytesIO(img_bytes)) for img_bytes in image_files]
    except Exception as exc:
        raise ValueError(f"Could not read one or more uploaded images: {exc}")

    # Determine the prompt based on the user's intent
    if combine:
        prompt_instruction = """
        These images represent a SINGLE recipe spread across multiple pages/photos. 
        Extract the information into ONE structured JSON object.
        Return ONLY a raw JSON object (dict) and absolutely no markdown formatting.
        """
    else:
        prompt_instruction = """
        These images contain MULTIPLE distinct recipes. 
        Extract EACH recipe you find into a separate object within a JSON array.
        Return ONLY a raw JSON array (list of dicts) and absolutely no markdown formatting.
        """

    prompt = f"""
    You are a helpful culinary assistant. {prompt_instruction}

    Use the exact following keys for each recipe object: 
    'name', 'description', 'image', 'servings', 'prep_time', 'cook_time', 'ingredients', 'instructions', 'notes', 'tags'. 

    CRITICAL TAGGING INSTRUCTIONS for the 'tags' key:
    Identify cooking method and equipment (e.g., "sheet pan", "slow cooker", "instant pot"). Also include general categories (e.g., "vegan", "dessert"). Provide a JSON array of 2 to 4 lowercase strings.
    
    For 'ingredients', format as a single string with each ingredient separated by a newline (\\n). 
    For 'instructions', format as a single string with numbered steps. 
    For 'notes', extract any baker's tips, storage instructions, or substitutions.
    If any information is missing, leave the value as an empty string ("").
    """

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        try:
            # Pass the text prompt followed by all image objects
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt] + imgs
            )
            
            text_response = response.text.strip()
            text_response = text_response.replace("```json", "").replace("```", "").strip()
            
            parsed_data = json.loads(text_response)
            
            # Normalize to a list so the frontend always deals with a list of recipes
            recipes = [parsed_data] if isinstance(parsed_data, dict) else parsed_data
            
            # Clean up keys for every recipe found
            expected_keys = ["name", "description", "image", "servings", "prep_time", "cook_time", "ingredients", "instructions", "notes", "tags"]
            for recipe_data in recipes:
                for key in expected_keys:
                    if key not in recipe_data:
                        recipe_data[key] = [] if key == "tags" else ""
                
                recipe_data["prep_time"] = clean_time_string(recipe_data.get("prep_time", ""))
                recipe_data["cook_time"] = clean_time_string(recipe_data.get("cook_time", ""))
                recipe_data["folder"] = ""
                    
            return recipes

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
                raise ValueError(f"Failed to extract recipe(s) using the AI model: {exc}")

def scrape_recipe_from_url(url: str) -> dict:
    """Fetch a webpage, attempt using web scraping first, then fall back to the Gemini API if needed."""
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

    html_content = response.text

    # --- Recipe Scraping Logic ---
    try:
        scraper = scrape_html(html_content, org_url=url)
        
        name = scraper.title()
        ingredients_list = scraper.ingredients()
        instructions_list = scraper.instructions_list()
        
        # Only proceed if we got the core requirements
        if name and ingredients_list and instructions_list:
            # Safely grab optional fields
            def safe_get(func, default=""):
                try:
                    val = func()
                    return str(val) if val else default
                except Exception:
                    return default

            recipe_data = {
                "name": name,
                "description": safe_get(scraper.description),
                "image": safe_get(scraper.image),
                "servings": safe_get(scraper.yields),
                "prep_time": safe_get(scraper.prep_time),
                "cook_time": safe_get(scraper.cook_time),
                "ingredients": "\n".join(ingredients_list),
                # Ensure instructions are numbered
                "instructions": "\n".join([f"{i+1}. {step}" for i, step in enumerate(instructions_list)]),
                "notes": "", # Hard to extract reliably without AI
                "tags": [],
                "source_url": url,
                "folder": ""
            }
            
            recipe_data["prep_time"] = clean_time_string(recipe_data["prep_time"])
            recipe_data["cook_time"] = clean_time_string(recipe_data["cook_time"])
            
            return recipe_data
            
    except Exception as e:
        # If the scraper fails or the site isn't supported, we silently catch it and move to Gemini
        print(f"Standard scraping failed or incomplete, falling back to Gemini... ({e})")

    # --- Gemini API Logic ---
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key not found.")

    client = genai.Client(api_key=api_key)
    cleaned_html = html.unescape(html_content[:100000])

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
    {cleaned_html}
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