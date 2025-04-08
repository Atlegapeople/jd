from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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
