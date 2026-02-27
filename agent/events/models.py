from pydantic import BaseModel
from typing import Optional

class Event(BaseModel):
    machine_name: str
    event_type: str
    description: str
    timestamp: str
    destination_ip: Optional[str] = None