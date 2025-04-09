import os
import sys
from pathlib import Path

# Add the current directory to the Python path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from dotenv import load_dotenv
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Load environment variables from .env in the backend directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

import mimetypes
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from bson.objectid import ObjectId
from pymongo import MongoClient
from datetime import datetime
import json
from typing import Union, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import pandas as pd
from io import BytesIO

# Import local modules
from models import ErrorCode, ErrorResponse, JobResponse, CandidateResponse, MatchRequest, MatchResponse, MatchRecord, JobInfo, CandidateInfo
from matcher import process_matches, get_job, get_candidates
from database import db, init_db, get_job, get_matches, get_reports, get_report
from doc_parser import parse_document

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_CONTENT_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
]

def create_error_response(code: ErrorCode, message: str, details: str = None) -> JSONResponse:
    error = ErrorResponse(
        code=code,
        message=message,
        details=details
    )
    return JSONResponse(
        status_code=get_status_code(code),
        content=json.loads(json.dumps(error.dict(), cls=MongoJSONEncoder))
    )

def get_status_code(error_code: ErrorCode) -> int:
    status_codes = {
        ErrorCode.INVALID_FILE_TYPE: 400,
        ErrorCode.FILE_TOO_LARGE: 400,
        ErrorCode.EMPTY_FILE: 400,
        ErrorCode.PARSING_ERROR: 500,
        ErrorCode.DATABASE_ERROR: 500,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.INVALID_ID: 400,
        ErrorCode.UNKNOWN_ERROR: 500
    }
    return status_codes.get(error_code, 500)

# Custom JSON encoder to handle ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    try:
        # Initialize database
        await init_db()
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Closed MongoDB connection")

@app.post("/upload", response_model=Union[JobResponse, CandidateResponse])
async def upload_and_parse(
    file: UploadFile,
    is_job: bool = Form(False)
) -> Union[JobResponse, CandidateResponse]:
    """
    Upload and parse a document (job description or CV).
    
    Args:
        file: The uploaded file
        is_job: Whether this is a job description (True) or CV (False)
    """
    try:
        # Validate file size (10MB limit)
        file_size = 0
        file_bytes = bytearray()
        
        # Read file in chunks to check size
        chunk_size = 1024 * 1024  # 1MB chunks
        while chunk := await file.read(chunk_size):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:  # 10MB limit
                raise HTTPException(
                    status_code=413,
                    detail=ErrorResponse(
                        code=ErrorCode.FILE_TOO_LARGE,
                        message="File size exceeds maximum limit of 10MB",
                        details=f"File size: {file_size / 1024 / 1024:.1f}MB",
                        timestamp=datetime.utcnow()
                    ).dict()
                )
            file_bytes.extend(chunk)
            
        # Validate content type
        content_type = file.content_type
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=415,
                detail=ErrorResponse(
                    code=ErrorCode.INVALID_FILE_TYPE,
                    message="Unsupported file type",
                    details=f"Content type: {content_type}",
                    timestamp=datetime.utcnow()
                ).dict()
            )
            
        # Parse the document
        try:
            cleaned_text, metadata = parse_document(bytes(file_bytes), content_type, "job" if is_job else "candidate")
        except Exception as e:
            logger.error(f"Error parsing document: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    code=ErrorCode.PARSING_ERROR,
                    message="Error parsing document",
                    details=str(e),
                    timestamp=datetime.utcnow()
                ).dict()
            )
        
        if is_job:
            # Create job document
            job_doc = {
                "filename": file.filename,
                "content_type": content_type,
                "text": cleaned_text,
                "word_count": metadata["word_count"],
                "parse_score": metadata["parse_score"],
                "preview": metadata["preview"],
                "extracted_info": metadata["extracted_info"],
                "created_at": datetime.utcnow(),
                "status": "processing"  # Initial status
            }
            
            # Insert into MongoDB
            try:
                result = await db.jobs.insert_one(job_doc)
                job_id = str(result.inserted_id)
                
                # Start async processing
                asyncio.create_task(process_job_with_claude(job_id, job_doc))
                
                return JobResponse(
                    job_id=job_id,
                    filename=file.filename,
                    content_type=content_type,
                    text=cleaned_text,
                    word_count=metadata["word_count"],
                    parse_score=metadata["parse_score"],
                    preview=metadata["preview"],
                    extracted_info=metadata["extracted_info"],
                    created_at=metadata["created_at"],
                    status="processing"
                )
            except Exception as e:
                logger.error(f"Error inserting job into database: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=ErrorResponse(
                        code=ErrorCode.DATABASE_ERROR,
                        message="Error saving job to database",
                        details=str(e),
                        timestamp=datetime.utcnow()
                    ).dict()
                )
        else:
            # Create candidate document
            candidate_doc = {
                "filename": file.filename,
                "content_type": content_type,
                "text": cleaned_text,
                "word_count": metadata["word_count"],
                "parse_score": metadata["parse_score"],
                "preview": metadata["preview"],
                "extracted_info": metadata["extracted_info"],
                "created_at": datetime.utcnow(),
                "status": "processing"  # Initial status
            }
            
            # Insert into MongoDB
            try:
                result = await db.candidates.insert_one(candidate_doc)
                candidate_id = str(result.inserted_id)
                
                # Start async processing
                asyncio.create_task(process_candidate_with_claude(candidate_id, candidate_doc))
                
                return CandidateResponse(
                    candidate_id=candidate_id,
                    filename=file.filename,
                    content_type=content_type,
                    text=cleaned_text,
                    word_count=metadata["word_count"],
                    parse_score=metadata["parse_score"],
                    preview=metadata["preview"],
                    extracted_info=metadata["extracted_info"],
                    created_at=metadata["created_at"],
                    status="processing"
                )
            except Exception as e:
                logger.error(f"Error inserting candidate into database: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=ErrorResponse(
                        code=ErrorCode.DATABASE_ERROR,
                        message="Error saving candidate to database",
                        details=str(e),
                        timestamp=datetime.utcnow()
                    ).dict()
                )
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code=ErrorCode.PROCESSING_ERROR,
                message="Error processing document",
                details=str(e),
                timestamp=datetime.utcnow()
            ).dict()
        )

async def process_job_with_claude(job_id: str, job_doc: dict):
    """Process job with Claude AI asynchronously"""
    try:
        # Get Claude assessment
        job_info = JobInfo(**job_doc.get('extracted_info', {}))
        claude_result = get_claude_match(job_info, None)  # Pass None for candidate as we're just processing the job
        
        # Update job document with Claude results
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "completed",
                    "claude_analysis": claude_result,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    except Exception as e:
        logger.error(f"Error processing job with Claude: {str(e)}")
        await db.jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                    "updated_at": datetime.utcnow()
                }
            }
        )

async def process_candidate_with_claude(candidate_id: str, candidate_doc: dict):
    """Process candidate with Claude AI asynchronously"""
    try:
        # Get Claude assessment
        candidate_info = CandidateInfo(**candidate_doc.get('extracted_info', {}))
        claude_result = get_claude_match(None, candidate_info)  # Pass None for job as we're just processing the candidate
        
        # Update candidate document with Claude results
        await db.candidates.update_one(
            {"_id": ObjectId(candidate_id)},
            {
                "$set": {
                    "status": "completed",
                    "claude_analysis": claude_result,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    except Exception as e:
        logger.error(f"Error processing candidate with Claude: {str(e)}")
        await db.candidates.update_one(
            {"_id": ObjectId(candidate_id)},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                    "updated_at": datetime.utcnow()
                }
            }
        )

@app.get("/jobs/all", response_model=list[JobResponse])
async def get_all_jobs():
    try:
        cursor = db.jobs.find()
        jobs = []
        async for job in cursor:
            job["job_id"] = str(job["_id"])
            del job["_id"]
            jobs.append(JobResponse(**job))
        return jobs
    except Exception as e:
        logger.error(f"Error getting all jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code=ErrorCode.DATABASE_ERROR,
                message="Error retrieving jobs",
                details=str(e),
                timestamp=datetime.utcnow()
            ).dict()
        )

@app.get("/jobs/{file_id}/text")
async def get_job_text(file_id: str):
    try:
        # Validate file_id format
        if not file_id or not ObjectId.is_valid(file_id):
            logger.error(f"Invalid file_id format: {file_id}")
            return JSONResponse(
                status_code=400, 
                content={"error": "Invalid file ID format"}
            )

        # Try to find the document by either _id or file_id
        try:
            job = await db.jobs.find_one({
                "$or": [
                    {"_id": ObjectId(file_id)},
                    {"file_id": file_id}
                ]
            })
        except Exception as e:
            logger.error(f"Database query failed for file_id {file_id}: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Database query failed: {str(e)}"}
            )

        # Check if document exists
        if not job:
            logger.warning(f"Job not found with file_id: {file_id}")
            return JSONResponse(
                status_code=404,
                content={"error": "Job not found"}
            )

        # Get text content
        text = job.get("text", "")
        if not text:
            logger.warning(f"No text content found for file_id: {file_id}")
            return JSONResponse(
                status_code=404,
                content={"error": "No text content found"}
            )

        # Return the text content
        return JSONResponse(content={"text": text})

    except Exception as e:
        logger.error(f"Error processing text request for file_id {file_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process request: {str(e)}"}
        )

@app.delete("/jobs/{file_id}")
async def delete_job(file_id: str):
    try:
        # Validate file_id format
        if not file_id or not ObjectId.is_valid(file_id):
            logger.error(f"Invalid file_id format: {file_id}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid file ID format"}
            )

        # Try to delete by either _id or file_id
        result = await db.jobs.delete_one({
            "$or": [
                {"_id": ObjectId(file_id)},
                {"file_id": file_id}
            ]
        })

        if result.deleted_count == 0:
            return JSONResponse(
                status_code=404,
                content={"error": "Job not found"}
            )

        return JSONResponse(
            status_code=200,
            content={"status": "deleted", "file_id": file_id}
        )

    except Exception as e:
        logger.error(f"Error deleting job {file_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete job: {str(e)}"}
        )

@app.delete("/jobs/all")
def delete_all_jobs():
    try:
        result = db.jobs.delete_many({})
        return JSONResponse(
            status_code=200,
            content={"status": "deleted", "count": result.deleted_count}
        )
    except Exception as e:
        logger.error(f"Error deleting all jobs: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete all jobs: {str(e)}"}
        )

@app.get("/candidates/all", response_model=list[CandidateResponse])
async def get_all_candidates():
    try:
        cursor = db.candidates.find()
        candidates = []
        async for candidate in cursor:
            candidate["candidate_id"] = str(candidate["_id"])
            del candidate["_id"]
            candidates.append(CandidateResponse(**candidate))
        return candidates
    except Exception as e:
        logger.error(f"Error getting all candidates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code=ErrorCode.DATABASE_ERROR,
                message="Error retrieving candidates",
                details=str(e),
                timestamp=datetime.utcnow()
            ).dict()
        )

@app.get("/candidates/{candidate_id}/text")
async def get_candidate_text(candidate_id: str):
    try:
        # Validate candidate_id format
        if not candidate_id or not ObjectId.is_valid(candidate_id):
            logger.error(f"Invalid candidate_id format: {candidate_id}")
            return JSONResponse(
                status_code=400, 
                content={"error": "Invalid candidate ID format"}
            )

        # Try to find the document by either _id or candidate_id
        try:
            candidate = await db.candidates.find_one({
                "$or": [
                    {"_id": ObjectId(candidate_id)},
                    {"candidate_id": candidate_id}
                ]
            })
        except Exception as e:
            logger.error(f"Database query failed for candidate_id {candidate_id}: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Database query failed: {str(e)}"}
            )

        # Check if document exists
        if not candidate:
            logger.warning(f"Candidate not found with candidate_id: {candidate_id}")
            return JSONResponse(
                status_code=404,
                content={"error": "Candidate not found"}
            )

        # Get text content
        text = candidate.get("text", "")
        if not text:
            logger.warning(f"No text content found for candidate_id: {candidate_id}")
            return JSONResponse(
                status_code=404,
                content={"error": "No text content found"}
            )

        # Return the text content
        return JSONResponse(content={"text": text})

    except Exception as e:
        logger.error(f"Error processing text request for candidate_id {candidate_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process request: {str(e)}"}
        )

@app.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str):
    try:
        # Validate candidate_id format
        if not candidate_id or not ObjectId.is_valid(candidate_id):
            logger.error(f"Invalid candidate_id format: {candidate_id}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid candidate ID format"}
            )

        # Try to delete by either _id or candidate_id
        result = await db.candidates.delete_one({
            "$or": [
                {"_id": ObjectId(candidate_id)},
                {"candidate_id": candidate_id}
            ]
        })

        if result.deleted_count == 0:
            return JSONResponse(
                status_code=404,
                content={"error": "Candidate not found"}
            )

        return JSONResponse(
            status_code=200,
            content={"status": "deleted", "candidate_id": candidate_id}
        )

    except Exception as e:
        logger.error(f"Error deleting candidate {candidate_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete candidate: {str(e)}"}
        )

@app.delete("/candidates/all")
def delete_all_candidates():
    try:
        result = db.candidates.delete_many({})
        return JSONResponse(
            status_code=200,
            content={"status": "deleted", "count": result.deleted_count}
        )
    except Exception as e:
        logger.error(f"Error deleting all candidates: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to delete all candidates: {str(e)}"}
        )

@app.post("/match")
async def match_candidates(request: MatchRequest):
    """Match candidates against a job description."""
    try:
        # Validate job_id format
        if not ObjectId.is_valid(request.job_id):
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    code=ErrorCode.INVALID_ID,
                    message="Invalid job ID format",
                    timestamp=datetime.utcnow().isoformat()
                ).dict()
            )
            
        # Validate candidate_ids format
        for cid in request.candidate_ids:
            if not ObjectId.is_valid(cid):
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponse(
                        code=ErrorCode.INVALID_ID,
                        message=f"Invalid candidate ID format: {cid}",
                        timestamp=datetime.utcnow().isoformat()
                    ).dict()
                )

        # Process matches using the matcher module
        result = await process_matches(request.job_id, request.candidate_ids)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    code=ErrorCode.NOT_FOUND,
                    message="No matches found",
                    timestamp=datetime.utcnow().isoformat()
                ).dict()
            )
            
        # Create and save report automatically
        report_id = None
        try:
            # Get job details
            job = await get_job(request.job_id)
            if not job:
                logger.warning(f"Job not found when creating report: {request.job_id}")
            else:
                # Prepare report data
                report_data = []
                for match in result.get('matches', []):
                    candidate = await get_candidates(match['candidate_id'])
                    if candidate:
                        report_data.append({
                            'name': candidate.get('name', 'Unknown'),
                            'email': candidate.get('email', ''),
                            'phone': candidate.get('phone', ''),
                            'current_role': candidate.get('current_role', ''),
                            'current_company': candidate.get('current_company', ''),
                            'python_score': match.get('python_score', 0),
                            'claude_score': match.get('claude_score', 0),
                            'shortlisted': match.get('shortlisted', False),
                            'strengths': match.get('claude_analysis', {}).get('strengths', []),
                            'gaps': match.get('claude_analysis', {}).get('gaps', [])
                        })
                
                # Create report document
                report_doc = {
                    'job_id': request.job_id,
                    'filename': f"match_results_{request.job_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                    'created_at': datetime.utcnow().isoformat(),
                    'content': report_data,
                    'status': 'completed',
                    'job_title': job.get('title', 'Unknown Job'),
                    'job_description': job.get('description', ''),
                    'total_candidates': len(report_data),
                    'shortlisted_candidates': len([c for c in report_data if c['shortlisted']])
                }
                
                # Save report to database
                logger.info(f"Attempting to save report for job_id: {request.job_id}")
                report_id = await save_report(report_doc)
                
                if report_id:
                    logger.info(f"Successfully saved report with ID: {report_id}")
                    logger.info(f"Report data: {json.dumps(report_doc, default=str)}")
                    
                    # Verify the report was saved
                    saved_report = await get_report(report_id)
                    if saved_report:
                        logger.info(f"Verified report exists in database with ID: {report_id}")
                    else:
                        logger.error(f"Report verification failed for ID: {report_id}")
                else:
                    logger.error(f"Failed to save report for job_id: {request.job_id}")
                
        except Exception as e:
            logger.error(f"Error saving automatic match report: {str(e)}")
            # Don't raise the error as we still want to return the match results
            
        # Return the result dictionary directly with the report_id added
        result['report_id'] = report_id
        return result
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in match_candidates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code=ErrorCode.PROCESSING_ERROR,
                message="Error processing match request",
                details=str(e),
                timestamp=datetime.utcnow().isoformat()
            ).dict()
        )

@app.post("/export/shortlisted/{job_id}")
async def export_shortlisted_report(job_id: str):
    try:
        logger.info(f"Starting report generation for job_id: {job_id}")
        
        # Validate job_id format
        if not ObjectId.is_valid(job_id):
            logger.error(f"Invalid job_id format: {job_id}")
            raise HTTPException(status_code=400, detail="Invalid job ID format")
            
        # Get job details
        logger.info(f"Fetching job details for job_id: {job_id}")
        job = await get_job(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Get matches for this job
        logger.info(f"Fetching matches for job_id: {job_id}")
        matches = await get_matches(job_id)
        if not matches:
            logger.error(f"No matches found for job_id: {job_id}")
            raise HTTPException(status_code=404, detail="No matches found for this job")
            
        # Filter for shortlisted candidates and validate data completeness
        valid_matches = []
        for match in matches:
            if not match.get('shortlisted', False):
                continue
                
            # Check for required fields
            required_fields = ['candidate_id', 'python_score', 'claude_score', 'claude_analysis']
            missing_fields = [field for field in required_fields if not match.get(field)]
            
            if missing_fields:
                logger.warning(f"Match {match.get('_id')} missing required fields: {missing_fields}")
                continue
                
            # Check for valid scores
            if not isinstance(match['python_score'], (int, float)) or not isinstance(match['claude_score'], (int, float)):
                logger.warning(f"Match {match.get('_id')} has invalid score types")
                continue
                
            # Check for valid claude_analysis
            claude_analysis = match.get('claude_analysis', {})
            if not isinstance(claude_analysis, dict) or not claude_analysis.get('strengths') or not claude_analysis.get('gaps'):
                logger.warning(f"Match {match.get('_id')} has invalid claude_analysis format")
                continue
                
            valid_matches.append(match)
            
        if not valid_matches:
            logger.error(f"No valid shortlisted candidates found for job_id: {job_id}")
            raise HTTPException(
                status_code=404,
                detail="No valid shortlisted candidates found. Please ensure all shortlisted candidates have complete match data."
            )
            
        logger.info(f"Found {len(valid_matches)} valid shortlisted candidates")
            
        # Get candidate details for valid matches
        candidates = []
        for match in valid_matches:
            candidate = await get_candidates(match['candidate_id'])
            if candidate:
                claude_analysis = match.get('claude_analysis', {})
                candidates.append({
                    'name': candidate.get('name', 'Unknown'),
                    'email': candidate.get('email', ''),
                    'phone': candidate.get('phone', ''),
                    'current_role': candidate.get('current_role', ''),
                    'current_company': candidate.get('current_company', ''),
                    'python_score': match['python_score'],
                    'claude_score': match['claude_score'],
                    'shortlisted': match['shortlisted'],
                    'strengths': claude_analysis.get('strengths', []),
                    'gaps': claude_analysis.get('gaps', [])
                })
        
        if not candidates:
            logger.error(f"No candidate details found for valid matches in job_id: {job_id}")
            raise HTTPException(
                status_code=404,
                detail="No candidate details found for valid matches"
            )
            
        # Create report document
        report_doc = {
            'job_id': job_id,
            'filename': f"shortlisted_candidates_{job_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            'created_at': datetime.utcnow().isoformat(),
            'content': candidates,
            'status': 'completed',
            'job_title': job.get('title', 'Unknown Job'),
            'job_description': job.get('description', ''),
            'total_candidates': len(candidates),
            'shortlisted_candidates': len([c for c in candidates if c['shortlisted']])
        }
        
        # Save report to database
        logger.info(f"Saving report to database for job_id: {job_id}")
        result = await db.reports.insert_one(report_doc)
        report_id = str(result.inserted_id)
        logger.info(f"Report saved successfully with ID: {report_id}")
        
        # Verify the report was saved
        saved_report = await get_report(report_id)
        if saved_report:
            logger.info(f"Verified report exists in database with ID: {report_id}")
        else:
            logger.error(f"Report verification failed for ID: {report_id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to verify report was saved"
            )
        
        return {
            'report_id': report_id,
            'filename': report_doc['filename'],
            'status': 'completed'
        }
        
    except HTTPException as e:
        logger.error(f"HTTP Exception in export_shortlisted_report: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error in export_shortlisted_report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report: {str(e)}"
        )

@app.get("/reports/{job_id}")
async def get_reports_endpoint(job_id: str):
    """
    Get all reports for a specific job.
    """
    try:
        logger.info(f"Fetching reports for job_id: {job_id}")
        
        if not ObjectId.is_valid(job_id):
            logger.error(f"Invalid job_id format: {job_id}")
            raise HTTPException(status_code=400, detail="Invalid job ID format")
            
        reports = await get_reports(job_id)
        logger.info(f"Found {len(reports)} reports for job_id: {job_id}")
        
        if not reports:
            logger.warning(f"No reports found for job_id: {job_id}")
            return []
            
        return reports
        
    except Exception as e:
        logger.error(f"Error getting reports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/download/{report_id}", response_class=JSONResponse)
async def download_report(report_id: str):
    """
    Download a specific report by ID.
    """
    try:
        if not ObjectId.is_valid(report_id):
            raise HTTPException(status_code=400, detail="Invalid report ID format")
            
        report = await get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
            
        # Return the report data directly
        return JSONResponse(
            content=report,
            headers={
                'Content-Disposition': f'attachment; filename="{report["filename"]}"',
                'Content-Type': 'application/json'
            }
        )
        
    except Exception as e:
        logger.error(f"Error downloading report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
