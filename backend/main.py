import os
import mimetypes
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from bson.objectid import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
import logging
from datetime import datetime
import json
from models import ErrorCode, ErrorResponse

# Load environment variables from .env
load_dotenv()

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

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

# Import your document parser
from doc_parser import parse_document

app = FastAPI()

# Enable CORS with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=False,  # Set to False for file uploads
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400  # Cache preflight requests for 24 hours
)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["jdparser"]
file_collection = db["files"]
candidate_collection = db["candidates"]  # New collection for candidates

logger = logging.getLogger(__name__)

@app.post("/jobs/parse")
async def upload_and_parse(file: UploadFile = File(...)):
    if not file:
        return JSONResponse(
            status_code=400,
            content={"error": "No file provided"}
        )

    try:
        # Read file content
        try:
            file_bytes = await file.read()
            if not file_bytes:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Empty file"}
                )
        except Exception as e:
            logger.error(f"Failed to read file: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={"error": f"Failed to read file: {str(e)}"}
            )

        # Determine content type
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0]
        if not content_type:
            return JSONResponse(
                status_code=400,
                content={"error": "Could not determine file type"}
            )

        # Validate file type
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        if content_type not in allowed_types:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unsupported file type: {content_type}. Only PDF and DOCX files are supported."}
            )

        # Parse document
        try:
            parsed = await parse_document(file_bytes, content_type)
            if not parsed:
                return JSONResponse(
                    status_code=500,
                    content={"error": "Document parsing returned no results"}
                )
        except Exception as e:
            logger.error(f"Document parsing failed: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to parse document: {str(e)}"}
            )

        # Prepare document for database
        try:
            # Create ObjectId first to ensure _id and file_id match
            doc_id = ObjectId()
            doc = {
                "_id": doc_id,
                "file_id": str(doc_id),  # Store file_id as string
                "filename": file.filename,
                "file_type": content_type,
                "raw_text": parsed.get("text", ""),
                "formatted_text": parsed.get("formatted_text", ""),
                "parse_score": parsed.get("parse_score", 0),
                "word_count": parsed.get("word_count", 0),
                "preview": parsed.get("preview", ""),
                "timestamp": parsed.get("timestamp", datetime.utcnow().isoformat()),
                "status": "completed",
                "is_image_based": parsed.get("is_image_based", False),
            }
        except Exception as e:
            logger.error(f"Failed to prepare document for database: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to prepare document: {str(e)}"}
            )

        # Save to database
        try:
            result = file_collection.insert_one(doc)
            return JSONResponse(
                status_code=200,
                content=json.loads(json.dumps(doc, cls=MongoJSONEncoder))
            )
        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to save to database: {str(e)}"}
            )

    except Exception as e:
        logger.error(f"Upload processing failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process upload: {str(e)}"}
        )

@app.get("/jobs/all")
def get_all_jobs():
    jobs = list(file_collection.find().sort("timestamp", -1))
    # Use the custom encoder for the entire response
    return JSONResponse(content=json.loads(json.dumps(jobs, cls=MongoJSONEncoder)))

@app.get("/jobs/{file_id}/text")
def get_job_text(file_id: str):
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
            job = file_collection.find_one({
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
        text = job.get("formatted_text") or job.get("raw_text", "") or job.get("text", "")
        if not text:
            logger.warning(f"No text content found for file_id: {file_id}")
            return JSONResponse(
                status_code=404,
                content={"error": "No text content found"}
            )

        # Convert the response to JSON using the custom encoder
        response_data = {"text": text}
        json_str = json.dumps(response_data, cls=MongoJSONEncoder)
        json_data = json.loads(json_str)

        # Return the text content
        return JSONResponse(content=json_data)

    except Exception as e:
        logger.error(f"Error processing text request for file_id {file_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process request: {str(e)}"}
        )

@app.delete("/jobs/{file_id}")
def delete_job(file_id: str):
    try:
        # Validate file_id format
        if not file_id or not ObjectId.is_valid(file_id):
            logger.error(f"Invalid file_id format: {file_id}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid file ID format"}
            )

        # Try to delete by either _id or file_id
        result = file_collection.delete_one({
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
        result = file_collection.delete_many({})
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

@app.post("/candidates/parse")
async def parse_candidate(file: UploadFile = File(...)):
    try:
        # Validate file type
        if not file.content_type in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            raise HTTPException(
                status_code=400,
                detail="Only PDF and DOCX files are supported"
            )
            
        # Read file content
        file_bytes = await file.read()
        
        # Parse document
        parsed = parse_document(file_bytes, file.content_type)
        
        # Create candidate document
        candidate_doc = {
            "filename": file.filename,
            "file_type": file.content_type,
            "text": parsed["text"],
            "word_count": parsed["word_count"],
            "parse_score": parsed["parse_score"],
            "preview": parsed["preview"],
            "extracted_info": parsed["extracted_info"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert into MongoDB
        result = candidate_collection.insert_one(candidate_doc)
        
        return {
            "message": "Candidate CV parsed successfully",
            "candidate_id": str(result.inserted_id),
            "filename": file.filename,
            "word_count": parsed["word_count"],
            "parse_score": parsed["parse_score"],
            "extracted_info": parsed["extracted_info"]
        }
        
    except Exception as e:
        logger.error(f"Error parsing candidate CV: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing candidate CV: {str(e)}"
        )

@app.get("/candidates/all")
def get_all_candidates():
    candidates = list(candidate_collection.find().sort("timestamp", -1))
    # Remove raw_text and formatted_text from response for brevity
    for candidate in candidates:
        candidate.pop("raw_text", None)
        candidate.pop("formatted_text", None)
    return JSONResponse(content=json.loads(json.dumps(candidates, cls=MongoJSONEncoder)))

@app.get("/candidates/{candidate_id}/text")
def get_candidate_text(candidate_id: str):
    try:
        # Validate candidate_id format
        if not candidate_id or not ObjectId.is_valid(candidate_id):
            return create_error_response(
                ErrorCode.INVALID_ID,
                "Invalid candidate ID format"
            )

        # Try to find the document
        try:
            candidate = candidate_collection.find_one({
                "$or": [
                    {"_id": ObjectId(candidate_id)},
                    {"candidate_id": candidate_id}
                ]
            })
        except Exception as e:
            logger.error(f"Database query failed: {str(e)}")
            return create_error_response(
                ErrorCode.DATABASE_ERROR,
                "Database query failed",
                str(e)
            )

        # Check if document exists
        if not candidate:
            return create_error_response(
                ErrorCode.NOT_FOUND,
                f"Candidate not found with ID: {candidate_id}"
            )

        # Get text content
        text = candidate.get("formatted_text") or candidate.get("raw_text", "") or candidate.get("text", "")
        if not text:
            return create_error_response(
                ErrorCode.NOT_FOUND,
                "No text content found"
            )

        response_data = {"text": text}
        return JSONResponse(
            content=json.loads(json.dumps(response_data, cls=MongoJSONEncoder))
        )

    except Exception as e:
        logger.error(f"Error retrieving candidate text: {str(e)}")
        return create_error_response(
            ErrorCode.UNKNOWN_ERROR,
            "Failed to retrieve candidate text",
            str(e)
        )

@app.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: str):
    try:
        # Validate candidate_id format
        if not candidate_id or not ObjectId.is_valid(candidate_id):
            logger.error(f"Invalid candidate_id format: {candidate_id}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid candidate ID format"}
            )

        # Try to delete by either _id or candidate_id
        result = candidate_collection.delete_one({
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
        result = candidate_collection.delete_many({})
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
