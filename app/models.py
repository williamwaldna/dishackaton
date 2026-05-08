from pydantic import BaseModel
from typing import Optional


class DocumentRecord(BaseModel):
    meeting_date: str
    case_folder: str
    case_type: Optional[str] = None
    case_id: Optional[str] = None
    document_title: str
    document_path: str
    document_type: Optional[str] = None
    text: str
