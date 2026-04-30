from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, schemas
import re 
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from transformers import pipeline
from newspaper import Article

# 1. INITIALIZE DATABASE
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. MODELS & TOOLS
class InputData(BaseModel):
    text: str = None
    url: str = None

analyzer = SentimentIntensityAnalyzer()
try:
    classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
except Exception as e:
    print("Transformers model failed to load:", e)
    classifier = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 3. ANALYSIS HELPERS
def extract_text(url):
    article = Article(url)
    article.download()
    article.parse()
    return article.text

def get_sensationalism(text):
    caps = len(re.findall(r'\b[A-Z]{2,}\b', text))
    exclam = text.count("!")
    sentiment = analyzer.polarity_scores(text)
    score = (caps * 0.2 + exclam * 0.2 + abs(sentiment["compound"]) * 0.6)
    return min(score, 1.0)

def detect_fake(text):
    if classifier is None: return 0.5
    result = classifier(text[:512])[0]
    return result["score"] if result["label"] == "NEGATIVE" else 1 - result["score"]

def ai_analyze(text, url=None):
    try:
        prompt = f"Verdict, reason(10 words) and Confidence (0-100) and give answer in True or False or unverified for: {text[:500]}"
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "phi3", "prompt": prompt, "stream": False},
            timeout=15
        )
        return response.json().get("response", "No AI response")
    except:
        return "AI unavailable right now"

# 4. API ENDPOINTS

@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # NO HASHING: Storing exactly what the user typed
    db_user = models.User(username=user.username, password=user.password)
    db.add(db_user)
    db.commit()
    return {"message": "User created (Plain Text Mode)"}

@app.post("/login")
def login(user: schemas.Login, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user:
        return {"error": "User not found"}
    
    # SIMPLE STRING COMPARISON
    if db_user.password != user.password:
        return {"error": "Wrong password"}
    
    return {"username": user.username, "status": "success"}

@app.post("/analyze")
def analyze(data: InputData, db: Session = Depends(get_db)): # Add db dependency here
    text = data.text
    if data.url and data.url.startswith("http"):
        try: text = extract_text(data.url)
        except: return {"error": "URL unreachable"}
    
    if not text: return {"error": "No text provided"}

    sens = get_sensationalism(text)
    ml_score = detect_fake(text)
    
    final_val = round(((1 - sens) * 0.3 + (1 - ml_score) * 0.7) * 100, 2)
    ai_result = ai_analyze(text, data.url)

    # --- NEW: AUTOMATIC SAVING ---
    label = "Uncertain"
    if final_val < 40: label = "Likely False"
    elif final_val > 70: label = "Likely True"

    new_history = models.History(
        username="GuestUser", # Default username
        text=text[:250],      # Storing a snippet
        score=final_val,
        label=label
    )
    db.add(new_history)
    db.commit() # This saves it to the database
    # -----------------------------

    return {
        "score": final_val,
        "ai_analysis": ai_result
    }

@app.post("/save")
def save(data: schemas.SaveInput, db: Session = Depends(get_db)):
    item = models.History(
        username=data.username,
        text=data.text,
        score=data.score,
        label=data.label
    )
    db.add(item)
    db.commit()
    return {"message": "Saved successfully"}

@app.get("/history/{username}")
def get_history(username: str, db: Session = Depends(get_db)):
    return db.query(models.History).filter(models.History.username == username).all()