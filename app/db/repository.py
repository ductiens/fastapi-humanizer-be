from typing import Dict, Any, List
from app.db.client import db
from app.core.config import settings

async def save_history_record(record: dict) -> str:
    collection = db.db[settings.MONGODB_COLLECTION_HISTORY]
    result = await collection.insert_one(record)
    return str(result.inserted_id)

async def get_history_records(username: str, limit: int = 50) -> List[dict]:
    collection = db.db[settings.MONGODB_COLLECTION_HISTORY]
    cursor = collection.find({"username": username}).sort("created_at", -1).limit(limit)
    records = []
    async for document in cursor:
        document["id"] = str(document["_id"])
        del document["_id"]
        records.append(document)
    return records

async def get_history_by_id(history_id: str) -> dict:
    from bson.objectid import ObjectId
    collection = db.db[settings.MONGODB_COLLECTION_HISTORY]
    document = await collection.find_one({"_id": ObjectId(history_id)})
    if document:
        document["id"] = str(document["_id"])
        del document["_id"]
    return document

async def get_user_by_username(username: str) -> dict:
    collection = db.db["users"]
    user = await collection.find_one({"username": username})
    if user:
        user["id"] = str(user["_id"])
        del user["_id"]
    return user

async def create_user(user_data: dict) -> str:
    collection = db.db["users"]
    result = await collection.insert_one(user_data)
    return str(result.inserted_id)
