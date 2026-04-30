from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

# ── USER SCHEMAS ──────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username for account")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")

    @validator("username")
    def username_alphanumeric(cls, v):
        assert v.isalnum(), "Username must be alphanumeric"
        return v.lower()

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True

class Login(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    username: str
    status: str
    message: Optional[str] = None

# ── ANALYSIS SCHEMAS ──────────────────────────────────────────────────────────
class AnalyzeInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to analyze")
    url: Optional[str] = Field(None, description="Source URL (optional)")
    username: Optional[str] = Field("GuestUser", description="Username checking the claim")

    @validator("text")
    def text_not_empty(cls, v):
        assert v.strip(), "Text cannot be empty or whitespace only"
        return v.strip()

class AnalysisResult(BaseModel):
    score: float = Field(..., ge=0, le=100, description="Truth score (0-100)")
    verdict: str = Field(..., description="Verdict: True, False, or Uncertain")
    reason: str = Field(..., description="Explanation of verdict")
    confidence: int = Field(..., ge=0, le=100, description="Confidence level (0-100)")

class AnalyzeResponse(BaseModel):
    score: float
    ai_analysis: str
    error: Optional[str] = None

    class Config:
        from_attributes = True

# ── HISTORY SCHEMAS ───────────────────────────────────────────────────────────
class HistoryItem(BaseModel):
    id: int
    username: str
    text: str
    score: float
    label: str
    source_url: Optional[str] = None
    confidence: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class HistoryCreate(BaseModel):
    username: str
    text: str
    score: float
    label: str
    source_url: Optional[str] = None
    confidence: Optional[int] = None

class SaveInput(BaseModel):
    username: str
    text: str
    score: float
    label: str
    source_url: Optional[str] = None
    confidence: Optional[int] = None

class HistoryResponse(BaseModel):
    message: str
    id: Optional[int] = None

    class Config:
        from_attributes = True

class HistoryListResponse(BaseModel):
    username: str
    items: List[HistoryItem]
    total: int

    class Config:
        from_attributes = True

# ── ERROR RESPONSE ────────────────────────────────────────────────────────────
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int