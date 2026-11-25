import os
import json
from pathlib import Path
from google import genai
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def get_crop_schedule(crop_name: str, state: str, season: str):
    try:
        if gemini_client is None:
            raise ValueError("Missing GEMINI_API_KEY")

        prompt = f"""
        Create a structured 3-month task schedule for growing {crop_name} in {state} during {season} season.
        Format the response as a JSON array with tasks containing:
        - week_number (1-12 for 3 months)
        - task_description
        - category (soil_preparation/planting/irrigation/fertilizer/pest_management)
        """
        
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        if not response.text:
            raise ValueError("No response from Gemini API")
            
        try:
            # Clean and parse the response
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            tasks = json.loads(cleaned_text)
            
            # Validate task structure
            for task in tasks:
                if not all(k in task for k in ('week_number', 'task_description', 'category')):
                    raise ValueError("Invalid task structure in response")
                
            return {
                "crop": crop_name,
                "state": state,
                "season": season,
                "tasks": tasks
            }
        except json.JSONDecodeError:
            raise ValueError("Gemini returned an invalid crop schedule")

    except Exception as e:
        print(f"Schedule generation error: {str(e)}")
        return None
