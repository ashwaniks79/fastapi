from sqlalchemy import Column, Integer, String, JSON, DateTime
from .database import Base

class RequestLog(Base):
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True))
    method = Column(String)
    path = Column(String)
    ip = Column(String)
    status_code = Column(Integer)
    process_time_ms = Column(Integer)
    user_agent = Column(String)
    additional_data = Column(JSON)  # For storing login attempts, API usage etc