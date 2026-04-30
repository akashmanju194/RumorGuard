"""
RumorGuard API - Production-grade backend using FastAPI, SQLAlchemy, and Pydantic.
Handles misinformation analysis, user authentication, and analysis history.
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# Import database and models
from data import SessionLocal, engine, get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
import models1 as models
import schema as schemas

# Import services
from auth import AuthService
from analysis import AnalysisService
from history import HistoryService

# ── 1. INITIALIZE DATABASE ────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

# ── 2. INITIALIZE APP ─────────────────────────────────────────────────────────
app = FastAPI(
    title="RumorGuard API",
    version="2.0.0",
    description="AI-powered fact-checking and misinformation detection",
)

# ── 3. MIDDLEWARE ─────────────────────────────────────────────────────────────
# NOTE: allow_origins=["*"] with allow_credentials=True is rejected by the
# Fetch spec.  Since we use JSON body auth (not cookies), credentials=False
# is correct and unblocks all cross-origin requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 4. INITIALIZE SERVICES ────────────────────────────────────────────────────
analysis_service = AnalysisService()
auth_service = AuthService()
history_service = HistoryService()

# ── 5. STATIC FILES & FRONTEND ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/", response_class=FileResponse)
def serve_frontend():
    """Serve try.html frontend"""
    return FileResponse(os.path.join(BASE_DIR, "try.html"))

# ── 6. DB SESSION DEPENDENCY ──────────────────────────────────────────────────
def get_db():
    """Dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── 7. HEALTH CHECK ───────────────────────────────────────────────────────────
@app.get("/health", response_model=dict)
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "RumorGuard API is running.",
        "version": "2.0.0",
    }

# ── 8. USER REGISTRATION ──────────────────────────────────────────────────────
@app.post(
    "/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    - **username**: Unique alphanumeric username (3-50 chars)
    - **password**: Account password (minimum 6 chars)
    """
    # Check if user exists
    existing_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        )

    # Hash password and create user
    hashed_password = auth_service.hash_password(user.password)
    new_user = models.User(
        username=user.username,
        password=hashed_password,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "username": new_user.username,
        "created_at": new_user.created_at
    }

# ── 9. LOGIN ──────────────────────────────────────────────────────────────────
@app.post(
    "/login",
    response_model=schemas.LoginResponse,
    summary="Authenticate user",
)
def login(credentials: schemas.Login, db: Session = Depends(get_db)):
    """
    Authenticate user and return login status.
    
    - **username**: User's registered username
    - **password**: User's password
    """
    # Find user by username
    db_user = db.query(models.User).filter(
        models.User.username == credentials.username
    ).first()

    # Verify credentials
    if not db_user or not auth_service.verify_password(
        credentials.password, db_user.password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    return schemas.LoginResponse(
        username=db_user.username,
        status="success",
    )

# ── 10. ANALYZE TEXT ──────────────────────────────────────────────────────────
@app.post(
    "/analyze",
    response_model=schemas.AnalyzeResponse,
    summary="Analyze text for misinformation",
)
def analyze(
    data: schemas.AnalyzeInput,
    db: Session = Depends(get_db),
):
    """
    Analyze text using VADER sentiment + pattern matching.
    
    Returns analysis result and saves to guest history.
    
    - **text**: Text to analyze (1-5000 chars)
    - **url**: Optional source URL
    """
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text provided.",
        )

    # Run analysis using service
    result = analysis_service.analyze(text)
    
    # Save to history under the specified user
    record_id = None
    try:
        history_data = schemas.SaveInput(
            username=data.username,
            text=text[:500],
            score=float(result["score"]),
            label=result["verdict"],
            source_url=data.url or None,
            confidence=result["confidence"],
        )
        saved_record = history_service.save_analysis(db, history_data)
        record_id = saved_record.id
    except Exception as e:
        # Log error but don't fail the response
        print(f"History save error: {e}")

    # Build analysis string
    ai_analysis_str = (
        f"Verdict: {result['verdict']}\n"
        f"Reason: {result['reason']}\n"
        f"Confidence: {result['confidence']}%"
    )

    return schemas.AnalyzeResponse(
        score=result["score"],
        ai_analysis=ai_analysis_str,
        error=None,
        id=record_id,
    )

# ── 11. SAVE ANALYSIS TO HISTORY ──────────────────────────────────────────────
@app.post(
    "/save",
    response_model=schemas.HistoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save analysis result",
)
def save_history(
    data: schemas.SaveInput,
    db: Session = Depends(get_db),
):
    """
    Save an analysis result to user's history.
    
    - **username**: User's username
    - **text**: Original analyzed text
    - **score**: Truth score (0-100)
    - **label**: Verdict (True/False/Uncertain)
    - **source_url**: Optional source URL
    - **confidence**: Confidence level (0-100)
    """
    try:
        record = history_service.save_analysis(db, data)
        return schemas.HistoryResponse(
            message="Saved successfully.",
            id=record.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save history: {str(e)}",
        )

# ── 12. GET USER HISTORY ──────────────────────────────────────────────────────
@app.get(
    "/history/{username}",
    response_model=schemas.HistoryListResponse,
    summary="Get user's analysis history",
)
async def get_history(
    username: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Retrieve user's past analysis results asynchronously.
    
    - **username**: Username to fetch history for
    - **limit**: Maximum items to return (default: 50)
    """
    result = await history_service.get_user_history_async(db, username, limit=limit)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return result

# ── 13. GET USER STATISTICS ───────────────────────────────────────────────────
@app.get(
    "/stats/{username}",
    response_model=dict,
    summary="Get user's analysis statistics",
)
def get_stats(username: str, db: Session = Depends(get_db)):
    """
    Get aggregate statistics for a user's analyses.
    
    Returns total analyses, average score, and verdict breakdown.
    """
    stats = history_service.get_user_stats(db, username)
    return {
        "username": username,
        **stats,
    }

# ── 14. DELETE HISTORY ITEM ───────────────────────────────────────────────────
@app.delete(
    "/history/{username}/{item_id}",
    response_model=dict,
    summary="Delete a history item",
)
def delete_history_item(
    username: str,
    item_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a specific analysis from user's history.
    
    - **username**: User's username (for authorization)
    - **item_id**: History item ID to delete
    """
    if history_service.delete_history_item(db, item_id, username):
        return {"message": "History item deleted successfully."}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History item not found or unauthorized.",
        )

# ── 15. GET SHARED ANALYSIS ─────────────────────────────────────────────────────
@app.get(
    "/api/share/{item_id}",
    response_model=schemas.HistoryItem,
    summary="Get a shared analysis result",
)
def get_shared_analysis(item_id: int, db: Session = Depends(get_db)):
    """
    Retrieve an analysis result by its ID for sharing.
    Does not require authentication.
    """
    item = db.query(models.History).filter(models.History.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared analysis not found.",
        )
    return item

from fastapi.responses import JSONResponse

# ── 16. ERROR HANDLERS ────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)