from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class ErrorCode(str, Enum):
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EMPTY_FILE = "EMPTY_FILE"
    PARSING_ERROR = "PARSING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INVALID_ID = "INVALID_ID"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class ErrorResponse(BaseModel):
    code: ErrorCode
    message: str
    details: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

    class Config:
        orm_mode = True
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
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class BatchParsedJobResponse(BaseModel):
    jobs: List[ParsedJobResponse]
    
    def __getitem__(self, index):
        return self.jobs[index]
    
    def __iter__(self):
        return iter(self.jobs)

class ParsedJobDetail(BaseModel):
    file_id: str
    filename: str
    text: str
    word_count: int
    parse_score: float
    parsed_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CandidateResponse(BaseModel):
    candidate_id: str
    filename: str
    file_type: Optional[str] = None
    word_count: int
    parse_score: float
    preview: str
    timestamp: datetime
    is_image_based: bool = False
    status: str = "completed"
    error_message: Optional[str] = None

    class Config:
        orm_mode = True
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
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
