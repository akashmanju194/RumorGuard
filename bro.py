from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, schemas
import re
import os

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ── 1. INITIALIZE DATABASE ────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="RumorGuard API", version="1.0.0")

# ── 2. CORS — allow frontend (file:// or localhost) to reach this API ─────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 3. SERVE index.html at "/" ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/", response_class=FileResponse)
def serve_frontend():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# ── 4. REQUEST MODEL (matches what index.html sends) ─────────────────────────
class InputData(BaseModel):
    text: str = ""
    url: str = ""

# ── 5. DB SESSION DEPENDENCY ──────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── 6. ANALYSIS ENGINE (VADER + rule-based, no heavy ML deps) ─────────────────
analyzer = SentimentIntensityAnalyzer()

RUMOUR_PATTERNS = [
    r"\bgovernment (is )?hiding\b",
    r"\bthey don'?t want you to know\b",
    r"\bwake up (sheeple|people)\b",
    r"\bconspiracy\b",
    r"\bcure(s)? (cancer|covid|diabetes|aids|all)\b",
    r"\b5g (causes?|spreads?|gives?|kills?)\b",
    r"\bmicrochip\b",
    r"\bdeep state\b",
    r"\bplandemic\b",
    r"\bnew world order\b",
    r"\bflat earth\b",
    r"\bvaccines? (causes?|gave|gives?|cause)\b",
    r"\bchip(ped)? in (the )?vaccine\b",
    r"\bsecret (agenda|plan|plot)\b",
    r"\bmind control\b",
    r"\bsheeple\b",
]

CREDIBLE_PHRASES = [
    r"\baccording to (scientists?|researchers?|doctors?|studies?|who|cdc|nih|nasa)\b",
    r"\bpeer[- ]reviewed\b",
    r"\bpublished in\b",
    r"\bclinical trial\b",
    r"\bstatistically significant\b",
    r"\bscientific consensus\b",
    r"\bdata shows?\b",
    r"\bresearch (shows?|suggests?|found)\b",
]

def ai_analyze(text: str) -> dict:
    """
    Lightweight rumour-detection engine using VADER + pattern rules.
    Returns { score (0-100, higher = more credible), verdict, reason, confidence }
    """
    text_lower = text.lower()
    scores = analyzer.polarity_scores(text)

    rumour_hits  = sum(1 for p in RUMOUR_PATTERNS  if re.search(p, text_lower))
    credible_hits = sum(1 for p in CREDIBLE_PHRASES if re.search(p, text_lower))

    caps_ratio      = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    exclamation_cnt = text.count("!")
    all_caps_words  = sum(1 for w in text.split() if w.isupper() and len(w) > 2)

    # Start neutral
    truth_score = 50.0
    truth_score += credible_hits * 12
    truth_score -= rumour_hits  * 15
    if scores["compound"] < -0.5:
        truth_score -= 10
    elif scores["compound"] > 0.3:
        truth_score += 5
    if caps_ratio > 0.3:    truth_score -= 10
    if exclamation_cnt >= 2: truth_score -= 8
    if all_caps_words >= 3:  truth_score -= 8

    truth_score = max(0.0, min(100.0, truth_score))

    # Verdict
    if truth_score >= 65:
        verdict = "True"
        reason  = "The claim uses credible, measured language with no obvious misinformation signals."
    elif truth_score >= 40:
        verdict = "Uncertain"
        reason  = "The claim has mixed signals — some credible markers but also emotional or unverified language."
    else:
        parts = []
        if rumour_hits    > 0:  parts.append("known conspiracy phrases")
        if scores["compound"] < -0.5: parts.append("highly fear-inducing sentiment")
        if caps_ratio > 0.3 or exclamation_cnt >= 2: parts.append("excessive capitalisation or exclamation marks")
        parts.append("no credible sourcing")
        verdict = "Likely False"
        reason  = "The claim shows misinformation signals: " + ", ".join(parts) + "."

    total_signals = (rumour_hits + credible_hits
                     + (1 if caps_ratio > 0.3 else 0)
                     + (1 if exclamation_cnt >= 2 else 0))
    confidence = min(95, 50 + total_signals * 8)
    if truth_score > 85 or truth_score < 15:
        confidence = min(95, confidence + 10)

    return {
        "score":      round(truth_score),
        "verdict":    verdict,
        "reason":     reason,
        "confidence": confidence,
    }


# ── 7. ANALYZE ENDPOINT ───────────────────────────────────────────────────────
@app.post("/analyze")
def analyze(data: InputData, db: Session = Depends(get_db)):
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="No text provided.")

    result = ai_analyze(text)

    # Save to history automatically as GuestUser
    db.add(models.History(
        username="GuestUser",
        text=text[:250],
        score=result["score"],
        label=result["verdict"],
    ))
    db.commit()

    # Build the string the frontend parses line-by-line
    ai_analysis_str = (
        f"Verdict: {result['verdict']}\n"
        f"Reason: {result['reason']}\n"
        f"Confidence: {result['confidence']}"
    )

    return {
        "score":       result["score"],
        "ai_analysis": ai_analysis_str,
        "error":       None,
    }


# ── 8. USER REGISTRATION ──────────────────────────────────────────────────────
@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists.")
    db.add(models.User(username=user.username, password=user.password))
    db.commit()
    return {"message": "User registered successfully."}


# ── 9. LOGIN ──────────────────────────────────────────────────────────────────
@app.post("/login")
def login(user: schemas.Login, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or db_user.password != user.password:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"username": user.username, "status": "success"}


# ── 10. SAVE HISTORY ──────────────────────────────────────────────────────────
@app.post("/save")
def save(data: schemas.SaveInput, db: Session = Depends(get_db)):
    db.add(models.History(
        username=data.username,
        text=data.text,
        score=data.score,
        label=data.label,
    ))
    db.commit()
    return {"message": "Saved successfully."}


# ── 11. GET HISTORY ───────────────────────────────────────────────────────────
@app.get("/history/{username}")
def get_history(username: str, db: Session = Depends(get_db)):
    return db.query(models.History).filter(models.History.username == username).all()


# ── 12. HEALTH CHECK ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "message": "RumorGuard API is running."}