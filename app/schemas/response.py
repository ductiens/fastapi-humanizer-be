from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class HumanizeResponse(BaseModel):
    success: bool
    original_text: str
    humanized_text: str
    error: Optional[str] = None
    history_id: Optional[str] = None

class HistoryRecordResponse(BaseModel):
    id: str
    original_text: str
    humanized_text: str
    style: str
    intensity_level: str
    language: str
    created_at: datetime
