from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from bson import ObjectId

class ErrorCode(str, Enum):
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EMPTY_FILE = "EMPTY_FILE"
    PARSING_ERROR = "PARSING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INVALID_ID = "INVALID_ID"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    API_ERROR = "API_ERROR"

class ErrorResponse(BaseModel):
    code: ErrorCode
    message: str
    details: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ParsedJobResponse(BaseModel):
    file_id: Optional[str] = None
    filename: str
    file_type: Optional[str] = None
    word_count: int
    parse_score: float
    preview: str
    status: str = "success"
    error_message: Optional[str] = None
    has_converted_pdf: bool = False
    upload_date: Optional[datetime] = None  # Added for frontend sorting

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class BatchParsedJobResponse(BaseModel):
    jobs: List[ParsedJobResponse]
    
    def __getitem__(self, index):
        return self.jobs[index]
    
    def __iter__(self):
        return iter(self.jobs)

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ParsedJobDetail(BaseModel):
    file_id: str
    filename: str
    text: str
    word_count: int
    parse_score: float
    parsed_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ExtractedJobInfo(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    responsibilities: List[str] = []
    requirements: List[str] = []
    skills: List[str] = []
    salary: Optional[str] = None
    benefits: List[str] = []

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ExtractedCandidateInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    education: List[Dict[str, Any]] = []
    experience: List[Dict[str, Any]] = []
    skills: List[str] = []
    languages: List[str] = []
    certifications: List[str] = []

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class JobInfo(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None
    summary: Optional[str] = None
    responsibilities: Optional[list[str]] = None
    requirements: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    salary: Optional[str] = None
    benefits: Optional[list[str]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CandidateInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    education: Optional[list[Dict[str, Any]]] = None
    experience: Optional[list[Dict[str, Any]]] = None
    skills: Optional[list[str]] = None
    languages: Optional[list[str]] = None
    certifications: Optional[list[str]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class JobResponse(BaseModel):
    job_id: str
    filename: str
    content_type: str
    text: str
    word_count: int
    parse_score: float
    preview: str
    extracted_info: JobInfo
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CandidateResponse(BaseModel):
    candidate_id: str
    filename: str
    content_type: str
    text: str
    word_count: int
    parse_score: float
    preview: str
    extracted_info: CandidateInfo
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CandidateDetail(BaseModel):
    candidate_id: str
    filename: str
    text: str
    word_count: int
    parse_score: float
    parsed_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MatchRequest(BaseModel):
    """Request model for matching candidates to a job."""
    job_id: str
    candidate_ids: List[str]

    class Config:
        schema_extra = {
            "example": {
                "job_id": "507f1f77bcf86cd799439011",
                "candidate_ids": ["507f1f77bcf86cd799439012", "507f1f77bcf86cd799439013"]
            }
        }

class MatchResult(BaseModel):
    candidate_id: str
    name: Optional[str] = None
    python_score: float
    claude_score: Optional[float] = None
    shortlist: Optional[bool] = None
    strengths: Optional[List[str]] = None
    gaps: Optional[List[str]] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MatchResponse(BaseModel):
    """Response model for matching candidates to a job."""
    job_id: str
    matches: List[Dict]
    total_candidates: int
    processed_candidates: int

    class Config:
        schema_extra = {
            "example": {
                "job_id": "507f1f77bcf86cd799439011",
                "matches": [
                    {
                        "candidate_id": "507f1f77bcf86cd799439012",
                        "python_score": 85.5,
                        "claude_score": 90.0,
                        "shortlist": True,
                        "claude_analysis": {
                            "match_score": 90.0,
                            "strengths": ["Strong technical background", "Relevant experience"],
                            "gaps": ["Limited cloud experience"]
                        }
                    }
                ],
                "total_candidates": 2,
                "processed_candidates": 2
            }
        }

class MatchRecord(BaseModel):
    job_id: str
    candidate_id: str
    python_score: float
    claude_score: Optional[float] = None
    shortlist: Optional[bool] = None
    strengths: Optional[List[str]] = None
    gaps: Optional[List[str]] = None
    timestamp: datetime = datetime.utcnow()

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class LogEntry(BaseModel):
    """Model for log entries."""
    id: Optional[str] = Field(None, alias="_id")
    level: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = None

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        json_schema_extra = {
            "example": {
                "level": "INFO",
                "message": "Sample log message",
                "timestamp": "2024-01-01T00:00:00",
                "metadata": {"key": "value"}
            }
        }
