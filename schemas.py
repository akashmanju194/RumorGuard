from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str

class Login(BaseModel):
    username: str
    password: str

class AnalyzeInput(BaseModel):
    text: str

class SaveInput(BaseModel):
    username: str
    text: str
    score: int
    label: str