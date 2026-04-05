import asyncio
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"Loaded API Key: {api_key[:10]}...")

genai.configure(api_key=api_key)

async def test_models():
    models = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-8b",
        "gemini-1.5-flash",
    ]
    for m in models:
        try:
            print(f"Testing model: {m}")
            model = genai.GenerativeModel(m)
            response = await model.generate_content_async("Hello")
            print(f"Success for {m}: {response.text[:20]}")
        except Exception as e:
            print(f"Error for {m}: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(test_models())
