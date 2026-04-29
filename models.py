from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True,index=True)
    username = Column(String, unique=True)
    password = Column(String)

class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    text = Column(String)
    score = Column(Integer)
    label = Column(String)