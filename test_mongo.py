import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")
MONGODB_COLLECTION_HISTORY = os.getenv("MONGODB_COLLECTION_HISTORY")

async def test_mongo():
    print(f"Connecting to MongoDB URI... (Length: {len(MONGODB_URI) if MONGODB_URI else 0})")
    client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DB_NAME]
    collection = db[MONGODB_COLLECTION_HISTORY]
    
    try:
        print("Pinging database...")
        await client.admin.command('ping')
        print("Ping successful! Trying to insert...")
        
        record = {"test": "data"}
        result = await collection.insert_one(record)
        print(f"Insert successful! ID: {result.inserted_id}")
        
    except Exception as e:
        print(f"MongoDB Error: {type(e).__name__} - {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_mongo())
