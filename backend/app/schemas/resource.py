from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.resource import ResourceType

class ResourceBase(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    resource_type: ResourceType

class ResourceCreate(ResourceBase):
    pass

class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    resource_type: Optional[ResourceType] = None

class ResourceResponse(ResourceBase):
    id: int
    knowledge_point_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True