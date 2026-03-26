import time
from typing import Any, Callable
from urllib.parse import urlparse
from io import BytesIO
import os
from PIL import Image

import json
import streamlit as st
from google import genai

import requests
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import (
    ElementNotFoundInHtml,
    FieldNotProvidedByWebsiteException,
    NoSchemaFoundInWildMode,
    WebsiteNotImplementedError,
)


def scrape_recipe_from_image(image_file: bytes) -> dict:
    """
    Extract recipe details from an image using the Gemini API.
    Returns a dictionary matching the expected recipe form keys.
    """
    # 1. Fetch the API key safely
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API key not found. Please add GEMINI_API_KEY to your Streamlit secrets.")

    client = genai.Client(api_key=api_key)

    # 2. Convert the bytes into a PIL Image format that the Gemini library expects
    try:
        img = Image.open(BytesIO(image_file))
    except Exception as exc:
        raise ValueError(f"Could not read the uploaded image: {exc}")

    # 3. Define the prompt to force the exact JSON schema your form expects
    prompt = (
        "You are a helpful culinary assistant. Please look at this recipe image "
        "and extract the information into a structured JSON format. "
        "Return ONLY a raw JSON object and absolutely no markdown formatting or backticks. "
        "Use the exact following keys: "
        "'name', 'description', 'servings', 'prep_time', 'cook_time', 'ingredients', 'instructions'. "
        "For 'ingredients', format it as a single string with each ingredient separated by a newline (\\n). "
        "For 'instructions', format it as a single string. "
        "If any information is missing from the image, leave the value as an empty string (\"\")."
    )

    # --- RETRY LOGIC ---
    max_retries = 3
    base_delay = 2  # Start with a 2-second delay

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, img]
            )
            
            # If successful, break out of the retry loop and process text
            text_response = response.text.strip()
            text_response = text_response.replace("```json", "").replace("```", "").strip()
            recipe_data = json.loads(text_response)
            
            expected_keys = ["name", "description", "servings", "prep_time", "cook_time", "ingredients", "instructions"]
            for key in expected_keys:
                if key not in recipe_data:
                    recipe_data[key] = ""
                    
            return recipe_data

        except Exception as exc:
            error_msg = str(exc)
            # Check if it's a 503/Unavailable error
            if "503" in error_msg or "UNAVAILABLE" in error_msg:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)  # Delays: 2s, 4s...
                    print(f"Server busy. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue # Try the loop again
                else:
                    raise ValueError("The AI model is currently experiencing exceptionally high traffic. Please wait a minute and try again.")
            else:
                # If it's a different error (like a bad API key or JSON decode issue), raise it immediately
                raise ValueError(f"Failed to extract recipe using the AI model: {exc}")

def scrape_recipe_from_url(url: str) -> dict:
    """
    Try to scrape recipe details from *url*.

    Returns a dict with recipe fields on success, or raises an exception with
    a human-readable message on failure.
    """
    # Validate URL scheme to prevent SSRF against internal services.
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
    except requests.exceptions.ConnectionError:
        raise ValueError("Could not connect to the website. Check the URL and try again.")
    except requests.exceptions.Timeout:
        raise ValueError("The request timed out. The website may be slow or unavailable.")
    except requests.exceptions.HTTPError as exc:
        raise ValueError(f"The website returned an error: {exc}")
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"Failed to fetch the URL: {exc}")

    try:
        scraper = scrape_html(response.text, org_url=url, wild_mode=True)
    except (NoSchemaFoundInWildMode, WebsiteNotImplementedError):
        raise ValueError(
            "Could not extract recipe data from this website. "
            "The site may not use a supported recipe format."
        )
    except Exception as exc:
        raise ValueError(f"An error occurred while parsing the recipe: {exc}")

    def safe_get(fn: Callable[[], Any], default: Any = "") -> Any:
        try:
            val = fn()
            return val if val else default
        except (ElementNotFoundInHtml, FieldNotProvidedByWebsiteException, Exception):
            return default

    ingredients_raw = safe_get(scraper.ingredients, "")
    if isinstance(ingredients_raw, list):
        ingredients = "\n".join(str(item) for item in ingredients_raw)
    elif isinstance(ingredients_raw, str):
        ingredients = ingredients_raw
    else:
        ingredients = ""

    instructions = safe_get(scraper.instructions, "")

    return {
        "name": safe_get(scraper.title, ""),
        "description": "",
        "image": safe_get(scraper.image, ""),
        "servings": str(safe_get(scraper.yields, "")),
        "prep_time": str(safe_get(scraper.prep_time, "")),
        "cook_time": str(safe_get(scraper.cook_time, "")),
        "ingredients": ingredients,
        "instructions": instructions,
        "source_url": url,
        "folder": "",
    }
