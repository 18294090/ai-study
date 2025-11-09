from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class KnowledgePointBase(BaseModel):
    name: str
    description: str

class KnowledgePointCreate(KnowledgePointBase):
    pass

class KnowledgePointResponse(KnowledgePointBase):
    id: int
    subject_id: int
    creator_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
