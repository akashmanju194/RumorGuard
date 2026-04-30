import streamlit as st
import requests
import sqlite3
from datetime import datetime

# --- CONFIGURATION & API SETUP ---
# Replace 'typeform/distilbert-base-uncased-mnli' with your preferred model if needed
API_URL = "https://api-inference.huggingface.co/models/typeform/distilbert-base-uncased-mnli"

# IMPORTANT: Ensure you add 'HF_TOKEN' in your Streamlit Cloud Secrets
headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}

# --- DATABASE SETUP (Local SQLite) ---
def init_db():
    conn = sqlite3.connect('rumours.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  claim TEXT, 
                  verdict TEXT, 
                  confidence REAL, 
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

def save_check(claim, verdict, confidence):
    conn = sqlite3.connect('rumours.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (claim, verdict, confidence, timestamp) VALUES (?, ?, ?, ?)",
              (claim, verdict, confidence, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# --- AI LOGIC ---
def query_model(payload):
    """Calls the HuggingFace Inference API"""
    response = requests.post(API_URL, headers=headers, json=payload)
    # If the model is loading, HuggingFace returns an 'estimated_time'
    return response.json()



# --- UI DESIGN (STREETWEAR/UTILITY THEME) ---
st.set_page_config(page_title="RumourGuard", page_icon="🛡️", layout="centered")

# Custom CSS for the "Utility" look
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #ff4b4b; color: white; }
    .stTextInput>div>div>input { background-color: #262730; color: white; border: 1px solid #464646; }
    </style>
    """, unsafe_allow_html=True) # Changed from unsafe_allow_stdio to unsafe_allow_html


st.title("🛡️ RUMOURGUARD")
st.caption("Advanced AI Misinformation Detection | v2.0 (Cloud Optimized)")

# --- MAIN INTERFACE ---
init_db()
tab1, tab2 = st.tabs(["Analyze Claim", "Recent Checks"])

with tab1:
    claim_input = st.text_area("ENTER CLAIM FOR VERIFICATION:", placeholder="e.g., 'Scientists discovered water on Mars last week'...")
    
    if st.button("RUN ANALYSIS"):
        if claim_input.strip():
            with st.spinner("QUERYING GLOBAL AI MODELS..."):
                payload = {
                    "inputs": claim_input,
                    "parameters": {"candidate_labels": ["True", "False", "Unverified", "Satire"]}
                }
                
                result = query_model(payload)
                
                # Check for errors (like model loading)
                if isinstance(result, dict) and "error" in result:
                    st.error(f"AI Engine Busy: {result['error']}. Please try again in 20 seconds.")
                elif isinstance(result, dict) and "labels" in result:
                    label = result['labels'][0]
                    score = result['scores'][0] * 100
                    
                    # Visual feedback
                    st.divider()
                    col1, col2 = st.columns(2)
                    col1.metric("VERDICT", label.upper())
                    col2.metric("CONFIDENCE", f"{score:.1f}%")
                    
                    # Save to DB
                    save_check(claim_input, label, score)
                    
                    st.success("Verification complete. Results logged to database.")
                else:
                    st.error("Unexpected response from AI Engine. Check your API token.")
        else:
            st.warning("Input required.")

with tab2:
    st.subheader("Database History")
    conn = sqlite3.connect('rumours.db')
    import pandas as pd
    df = pd.read_sql_query("SELECT timestamp, claim, verdict, confidence FROM history ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()

# --- SHARING LOGIC ---
st.sidebar.title("Tools")
if st.sidebar.button("Copy Shareable Link"):
    # Note: In a cloud environment, this is a simulated link. 
    # To make this real, you'd append ?id=XX to your streamlit URL
    st.sidebar.code("https://rumour-guard.streamlit.app/", language="text")
    st.sidebar.toast("Link generated in panel above!")