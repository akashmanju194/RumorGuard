from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.sql import func
from data import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    text = Column(String)
    score = Column(Float)  # Changed to Float for precision (0-100)
    label = Column(String)  # "True", "False", "Uncertain"
    source_url = Column(String, nullable=True)  # Optional source URL
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    confidence = Column(Integer, nullable=True)  # 0-100 confidence score