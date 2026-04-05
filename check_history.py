import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")
MONGODB_COLLECTION_HISTORY = os.getenv("MONGODB_COLLECTION_HISTORY")

async def check():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB_NAME]
    collection = db[MONGODB_COLLECTION_HISTORY]
    
    count = await collection.count_documents({})
    print(f"Total history records in DB: {count}")
    
    latest_records = await collection.find().sort("created_at", -1).limit(5).to_list(length=5)
    for r in latest_records:
        print(f"[{r.get('created_at')}] User: {r.get('username')}, ID: {r['_id']}")

    client.close()

if __name__ == "__main__":
    asyncio.run(check())
