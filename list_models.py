import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

try:
    models = genai.list_models()
    with open("models.txt", "w", encoding="utf-8") as f:
        for m in models:
            f.write(f"{m.name} - {m.supported_generation_methods}\n")
    print("Done")
except Exception as e:
    print(e)
