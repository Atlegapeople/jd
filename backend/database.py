from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from bson.errors import InvalidId
from typing import List, Dict, Optional, AsyncGenerator
import os
from dotenv import load_dotenv
import logging
import json

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

# Load environment variables
load_dotenv()

# MongoDB connection string
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "talenthub")

# Create MongoDB client
client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

# Initialize database collections and indexes
async def init_db():
    try:
        collections = ['jobs', 'candidates', 'matches', 'reports', 'logs']
        for collection in collections:
            if collection not in await db.list_collection_names():
                await db.create_collection(collection)
                logger.info(f"Created collection: {collection}")

        # Drop existing indexes except _id
        for name in ['jobs', 'candidates', 'matches', 'reports', 'logs']:
            indexes = await db[name].index_information()
            for index in indexes:
                if index != "_id_":
                    await db[name].drop_index(index)

        # Create required indexes
        await db.jobs.create_index("file_id", unique=True, sparse=True)
        await db.candidates.create_index("file_id", unique=True, sparse=True)
        await db.matches.create_index("job_id")
        await db.matches.create_index("candidate_id")
        await db.reports.create_index("job_id")
        await db.reports.create_index("created_at")
        await db.logs.create_index("timestamp")

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise e

async def get_db() -> AsyncGenerator:
    try:
        yield db
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise e

async def get_job(job_id: str) -> Optional[Dict]:
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if job:
            job["_id"] = str(job["_id"])
        return job
    except InvalidId:
        logger.error("Invalid job_id format")
        return None
    except Exception as e:
        logger.error(f"Error getting job: {str(e)}")
        return None

async def get_candidate(candidate_id: str) -> Optional[Dict]:
    try:
        candidate = await db.candidates.find_one({"_id": ObjectId(candidate_id)})
        if candidate:
            candidate["_id"] = str(candidate["_id"])
        return candidate
    except InvalidId:
        logger.error("Invalid candidate_id format")
        return None
    except Exception as e:
        logger.error(f"Error getting candidate: {str(e)}")
        return None

async def get_candidates(candidate_ids: List[str]) -> List[Dict]:
    try:
        object_ids = [ObjectId(cid) for cid in candidate_ids if ObjectId.is_valid(cid)]
        cursor = db.candidates.find({"_id": {"$in": object_ids}})
        candidates = await cursor.to_list(length=None)
        for candidate in candidates:
            candidate["_id"] = str(candidate["_id"])
        return candidates
    except Exception as e:
        logger.error(f"Error getting candidates: {str(e)}")
        return []

async def save_job(job: Dict) -> Optional[str]:
    try:
        result = await db.jobs.insert_one(job)
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Error saving job: {str(e)}")
        return None

async def save_candidate(candidate: Dict) -> Optional[str]:
    try:
        result = await db.candidates.insert_one(candidate)
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Error saving candidate: {str(e)}")
        return None

async def get_all_jobs() -> List[Dict]:
    try:
        cursor = db.jobs.find()
        jobs = await cursor.to_list(length=None)
        for job in jobs:
            job["_id"] = str(job["_id"])
        return jobs
    except Exception as e:
        logger.error(f"Error getting all jobs: {str(e)}")
        return []

async def get_all_candidates() -> List[Dict]:
    try:
        cursor = db.candidates.find()
        candidates = await cursor.to_list(length=None)
        for candidate in candidates:
            candidate["_id"] = str(candidate["_id"])
        return candidates
    except Exception as e:
        logger.error(f"Error getting all candidates: {str(e)}")
        return []

async def clear_database():
    try:
        await db.jobs.delete_many({})
        await db.candidates.delete_many({})
        return True
    except Exception as e:
        logger.error(f"Error clearing database: {str(e)}")
        return False

async def get_matches(job_id: str) -> List[Dict]:
    try:
        cursor = db.matches.find({"job_id": job_id})
        matches = await cursor.to_list(length=None)
        for match in matches:
            match["_id"] = str(match["_id"])
        return matches
    except Exception as e:
        logger.error(f"Error getting matches: {str(e)}")
        return []

async def save_report(report: Dict) -> Optional[str]:
    try:
        required_fields = ['job_id', 'filename', 'created_at', 'content', 'status']
        for field in required_fields:
            if field not in report:
                logger.error(f"Missing required field: {field}")
                return None

        if isinstance(report['job_id'], str):
            try:
                report['job_id'] = ObjectId(report['job_id'])
            except InvalidId:
                logger.error("Invalid job_id format in report")
                return None

        result = await db.reports.insert_one(report)
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Error saving report: {str(e)}")
        return None

async def get_reports(job_id: str) -> List[Dict]:
    try:
        cursor = db.reports.find({"job_id": ObjectId(job_id)}).sort("created_at", -1)
        reports = await cursor.to_list(length=None)
        for report in reports:
            report["id"] = str(report["_id"])
            del report["_id"]
        return reports
    except Exception as e:
        logger.error(f"Error getting reports: {str(e)}")
        return []

async def get_report(report_id: str) -> Optional[Dict]:
    try:
        report = await db.reports.find_one({"_id": ObjectId(report_id)})
        if report:
            report["id"] = str(report["_id"])
            del report["_id"]
        return report
    except Exception as e:
        logger.error(f"Error getting report: {str(e)}")
        return None
