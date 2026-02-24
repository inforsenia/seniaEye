from pydantic import BaseModel

class Event(BaseModel):
    machine_name: str
    event_type: str
    description: str
    timestamp: str