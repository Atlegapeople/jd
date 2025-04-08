from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    status = Column(String(50), default='processing')
    parse_score = Column(Float, default=0.0)
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Logs relationship
    logs = relationship("LogEntry", back_populates="job", cascade="all, delete-orphan")

class LogEntry(Base):
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    level = Column(String(20), default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship back to job
    job = relationship("Job", back_populates="logs")
