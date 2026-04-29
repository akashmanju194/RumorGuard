"""
Analysis Service: Rumor detection engine using VADER sentiment analysis + pattern matching.
Uses lightweight, rule-based detection without heavy ML dependencies.
"""
import re
from typing import Dict, Any
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class AnalysisService:
    """Handles rumor detection and analysis logic."""

    # Conspiracy and misinformation patterns
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

    # Credible sourcing patterns
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

    def __init__(self):
        """Initialize VADER sentiment analyzer."""
        self.analyzer = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze text for misinformation using VADER + pattern matching.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with keys: score, verdict, reason, confidence
        """
        text_lower = text.lower()
        scores = self.analyzer.polarity_scores(text)

        # Count pattern matches
        rumour_hits = sum(1 for p in self.RUMOUR_PATTERNS if re.search(p, text_lower))
        credible_hits = sum(1 for p in self.CREDIBLE_PHRASES if re.search(p, text_lower))

        # Linguistic markers
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        exclamation_cnt = text.count("!")
        all_caps_words = sum(1 for w in text.split() if w.isupper() and len(w) > 2)

        # Calculate truth score (0-100)
        truth_score = 50.0
        truth_score += credible_hits * 12
        truth_score -= rumour_hits * 15
        
        if scores["compound"] < -0.5:
            truth_score -= 10
        elif scores["compound"] > 0.3:
            truth_score += 5
            
        if caps_ratio > 0.3:
            truth_score -= 10
        if exclamation_cnt >= 2:
            truth_score -= 8
        if all_caps_words >= 3:
            truth_score -= 8

        truth_score = max(0.0, min(100.0, truth_score))

        # Determine verdict and reason
        if truth_score >= 65:
            verdict = "True"
            reason = "The claim uses credible, measured language with no obvious misinformation signals."
        elif truth_score >= 40:
            verdict = "Uncertain"
            reason = "The claim has mixed signals — some credible markers but also emotional or unverified language."
        else:
            parts = []
            if rumour_hits > 0:
                parts.append("known conspiracy phrases")
            if scores["compound"] < -0.5:
                parts.append("highly fear-inducing sentiment")
            if caps_ratio > 0.3 or exclamation_cnt >= 2:
                parts.append("excessive capitalisation or exclamation marks")
            if credible_hits == 0:
                parts.append("no credible sourcing")
            verdict = "Likely False"
            reason = "The claim shows misinformation signals: " + ", ".join(parts) + "."

        # Calculate confidence (0-100)
        total_signals = (
            rumour_hits + credible_hits
            + (1 if caps_ratio > 0.3 else 0)
            + (1 if exclamation_cnt >= 2 else 0)
        )
        confidence = min(95, 50 + total_signals * 8)
        if truth_score > 85 or truth_score < 15:
            confidence = min(95, confidence + 10)

        return {
            "score": round(truth_score),
            "verdict": verdict,
            "reason": reason,
            "confidence": confidence,
        }
