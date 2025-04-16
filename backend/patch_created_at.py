from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[os.getenv("DATABASE_NAME", "talenthub")]

async def fix_format(field: str) -> int:
    fixed = 0
    async for c in db.candidates.find({f"extracted_info.{field}": {"$exists": True}}):
        items = c["extracted_info"].get(field)
        if isinstance(items, list):
            new_items = []
            for item in items:
                if isinstance(item, dict):
                    new_items.append(item)
                elif isinstance(item, str):
                    new_items.append({"note": item})  # wrap string into dict
                else:
                    continue
            if new_items != items:
                await db.candidates.update_one(
                    {"_id": c["_id"]},
                    {"$set": {f"extracted_info.{field}": new_items}}
                )
                fixed += 1
    return fixed

async def main():
    edu = await fix_format("education")
    exp = await fix_format("experience")
    print(f"✅ Fixed education in {edu} docs")
    print(f"✅ Fixed experience in {exp} docs")

asyncio.run(main())
