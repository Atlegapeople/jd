from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import List, Dict, Optional, AsyncGenerator
import os
from dotenv import load_dotenv
import logging
import json

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# MongoDB connection string
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "talenthub")

# Create MongoDB client
client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

# Create collections if they don't exist
async def init_db():
    """Initialize database collections."""
    try:
        # Create collections if they don't exist
        collections = ['jobs', 'candidates', 'matches', 'reports', 'logs']
        for collection in collections:
            if collection not in await db.list_collection_names():
                await db.create_collection(collection)
                logger.info(f"Created collection: {collection}")
        
        # Drop existing indexes first
        await db.jobs.drop_indexes()
        await db.candidates.drop_indexes()
        await db.matches.drop_indexes()
        await db.reports.drop_indexes()
        await db.logs.drop_indexes()
        
        # Create indexes
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
    """Get database connection."""
    try:
        yield db
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise e

# Initialize database on startup
import asyncio
asyncio.create_task(init_db())

async def get_job(job_id: str) -> Optional[Dict]:
    """Get a job by ID."""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if job:
            job["_id"] = str(job["_id"])
        return job
    except Exception as e:
        print(f"Error getting job: {str(e)}")
        return None

async def get_candidates(candidate_ids: List[str]) -> List[Dict]:
    """Get candidates by IDs."""
    try:
        candidate_ids = [ObjectId(cid) for cid in candidate_ids]
        cursor = db.candidates.find({"_id": {"$in": candidate_ids}})
        candidates = await cursor.to_list(length=None)
        for candidate in candidates:
            candidate["_id"] = str(candidate["_id"])
        return candidates
    except Exception as e:
        print(f"Error getting candidates: {str(e)}")
        return []

async def save_job(job: Dict) -> str:
    """Save a job to the database."""
    try:
        result = await db.jobs.insert_one(job)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error saving job: {str(e)}")
        return None

async def save_candidate(candidate: Dict) -> str:
    """Save a candidate to the database."""
    try:
        result = await db.candidates.insert_one(candidate)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error saving candidate: {str(e)}")
        return None

async def get_all_jobs() -> List[Dict]:
    """Get all jobs."""
    try:
        cursor = db.jobs.find()
        jobs = await cursor.to_list(length=None)
        for job in jobs:
            job["_id"] = str(job["_id"])
        return jobs
    except Exception as e:
        print(f"Error getting all jobs: {str(e)}")
        return []

async def get_all_candidates() -> List[Dict]:
    """Get all candidates."""
    try:
        cursor = db.candidates.find()
        candidates = await cursor.to_list(length=None)
        for candidate in candidates:
            candidate["_id"] = str(candidate["_id"])
        return candidates
    except Exception as e:
        print(f"Error getting all candidates: {str(e)}")
        return []

async def clear_database():
    """Clear all data from the database."""
    try:
        await db.jobs.delete_many({})
        await db.candidates.delete_many({})
        return True
    except Exception as e:
        print(f"Error clearing database: {str(e)}")
        return False

async def get_matches(job_id: str) -> List[Dict]:
    """Get all matches for a specific job."""
    try:
        cursor = db.matches.find({"job_id": job_id})
        matches = await cursor.to_list(length=None)
        for match in matches:
            match["_id"] = str(match["_id"])
        return matches
    except Exception as e:
        print(f"Error getting matches: {str(e)}")
        return []

async def save_report(report: Dict) -> str:
    """Save a report to the database."""
    try:
        logger.info(f"Attempting to save report with data: {json.dumps(report, default=str)}")
        
        # Ensure required fields are present
        required_fields = ['job_id', 'filename', 'created_at', 'content', 'status']
        missing_fields = [field for field in required_fields if field not in report]
        if missing_fields:
            logger.error(f"Missing required fields in report: {missing_fields}")
            return None
            
        # Convert job_id to ObjectId if it's not already
        if isinstance(report['job_id'], str):
            report['job_id'] = ObjectId(report['job_id'])
            
        # Insert the report
        result = await db.reports.insert_one(report)
        report_id = str(result.inserted_id)
        
        # Verify the report was saved
        saved_report = await db.reports.find_one({"_id": result.inserted_id})
        if saved_report:
            logger.info(f"Successfully saved report with ID: {report_id}")
            return report_id
        else:
            logger.error(f"Failed to verify report was saved: {report_id}")
            return None
            
    except Exception as e:
        logger.error(f"Error saving report: {str(e)}")
        return None

async def get_reports(job_id: str) -> List[Dict]:
    """Get all reports for a specific job."""
    try:
        cursor = db.reports.find({"job_id": job_id}).sort("created_at", -1)
        reports = await cursor.to_list(length=None)
        for report in reports:
            report["id"] = str(report["_id"])
            del report["_id"]
        return reports
    except Exception as e:
        print(f"Error getting reports: {str(e)}")
        return []

async def get_report(report_id: str) -> Optional[Dict]:
    """Get a report by ID."""
    try:
        report = await db.reports.find_one({"_id": ObjectId(report_id)})
        if report:
            report["id"] = str(report["_id"])
            del report["_id"]
        return report
    except Exception as e:
        print(f"Error getting report: {str(e)}")
        return None
