"""
Analysis Service: Hybrid rumour detection engine.

Architecture (Option B — Transformers):
  1. HuggingFace Zero-Shot Classification
     Model: typeform/distilbert-base-uncased-mnli
     Scores the claim against candidate labels:
       ["misinformation or fake news", "credible or factual information"]
     This gives a principled, pre-trained probability that the text is
     misinformative, without requiring a domain-specific fine-tune.

  2. VADER Sentiment Analysis
     Captures emotional extremism that the NLI model may miss in short texts.

  3. Heuristic Pattern Matching
     Hard-coded conspiracy / credibility signals that are very precise
     (e.g. "government is hiding", "peer-reviewed").

  4. Ensemble Weighting
     transformer_score  : 50%
     vader_score        : 20%
     pattern_score      : 30%

  Lazy loading ensures the model is only downloaded once on first request
  and cached in memory for subsequent calls.
"""
import re
import threading
from typing import Dict, Any, Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# ── Thread-safe lazy loader ────────────────────────────────────────────────────
_pipeline = None
_pipeline_lock = threading.Lock()
_pipeline_error: Optional[str] = None   # set if load fails; fallback to VADER


def _get_pipeline():
    """Return the cached zero-shot pipeline, loading it on first call."""
    global _pipeline, _pipeline_error
    if _pipeline is not None or _pipeline_error is not None:
        return _pipeline

    with _pipeline_lock:
        if _pipeline is not None or _pipeline_error is not None:
            return _pipeline
        try:
            from transformers import pipeline as hf_pipeline
            print("[RumorGuard] Loading HuggingFace model: typeform/distilbert-base-uncased-mnli …")
            _pipeline = hf_pipeline(
                "zero-shot-classification",
                model="typeform/distilbert-base-uncased-mnli",
                device=-1,          # CPU; set to 0 for GPU
            )
            print("[RumorGuard] Model loaded successfully.")
        except Exception as exc:                         # pragma: no cover
            _pipeline_error = str(exc)
            print(f"[RumorGuard] WARNING: could not load transformer model: {exc}")
            print("[RumorGuard] Falling back to VADER-only mode.")
    return _pipeline


# ── Candidate labels for zero-shot classification ─────────────────────────────
CANDIDATE_LABELS = [
    "misinformation or fake news",
    "credible or factual information",
]


class AnalysisService:
    """
    Hybrid rumour detector:
      HuggingFace NLI (50%) + VADER (20%) + Pattern heuristics (30%)
    """

    # ── Conspiracy / misinformation lexicon ───────────────────────────────────
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
        r"\bcrisis actor\b",
        r"\bshadow government\b",
        r"\billuminati\b",
    ]

    # ── Credibility signals ────────────────────────────────────────────────────
    CREDIBLE_PHRASES = [
        r"\baccording to (scientists?|researchers?|doctors?|studies?|who|cdc|nih|nasa)\b",
        r"\bpeer[- ]reviewed\b",
        r"\bpublished in\b",
        r"\bclinical trial\b",
        r"\bstatistically significant\b",
        r"\bscientific consensus\b",
        r"\bdata shows?\b",
        r"\bresearch (shows?|suggests?|found)\b",
        r"\bfact[- ]checked\b",
        r"\breplication study\b",
    ]

    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        # Kick off model loading in the background so first request is faster
        threading.Thread(target=_get_pipeline, daemon=True).start()

    # ── Internal scoring helpers ───────────────────────────────────────────────

    def _transformer_truth_score(self, text: str) -> Optional[float]:
        """
        Run zero-shot classification and return a truth score 0-100.
        Returns None if the model is unavailable.
        """
        pipe = _get_pipeline()
        if pipe is None:
            return None

        try:
            result = pipe(text[:512], candidate_labels=CANDIDATE_LABELS, multi_label=False)
            label_scores = dict(zip(result["labels"], result["scores"]))
            credible_prob = label_scores.get("credible or factual information", 0.5)
            # Map [0, 1] probability to [0, 100] truth score
            return round(credible_prob * 100, 2)
        except Exception as exc:                         # pragma: no cover
            print(f"[RumorGuard] Transformer inference error: {exc}")
            return None

    def _vader_truth_score(self, text: str) -> float:
        """
        Derive a truth-likelihood score from VADER compound sentiment.
        Range: 0-100.  Extremely negative = lower score.
        """
        scores = self.vader.polarity_scores(text)
        compound = scores["compound"]          # -1 … +1
        # Rescale: compound -1 → 20, 0 → 50, +1 → 80
        return round(50.0 + compound * 30.0, 2)

    def _pattern_truth_score(self, text: str) -> float:
        """
        Count rumour / credibility pattern hits and return a truth score 0-100.
        Starts at 50, each credible hit +12, each rumour hit -15.
        Linguistic abuse signals (ALL CAPS, excessive !!!) penalised further.
        """
        text_lower = text.lower()
        rumour_hits = sum(1 for p in self.RUMOUR_PATTERNS if re.search(p, text_lower))
        credible_hits = sum(1 for p in self.CREDIBLE_PHRASES if re.search(p, text_lower))

        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        exclamation_cnt = text.count("!")
        all_caps_words = sum(1 for w in text.split() if w.isupper() and len(w) > 2)

        score = 50.0
        score += credible_hits * 12
        score -= rumour_hits * 15
        if caps_ratio > 0.3:
            score -= 10
        if exclamation_cnt >= 2:
            score -= 8
        if all_caps_words >= 3:
            score -= 8

        return round(max(0.0, min(100.0, score)), 2)

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Full hybrid analysis pipeline.

        Returns:
            dict with keys: score, verdict, reason, confidence
        """
        # 1. Component scores
        transformer_score = self._transformer_truth_score(text)
        vader_score = self._vader_truth_score(text)
        pattern_score = self._pattern_truth_score(text)

        # 2. Weighted ensemble
        if transformer_score is not None:
            truth_score = (
                transformer_score * 0.50
                + vader_score       * 0.20
                + pattern_score     * 0.30
            )
            method = "transformer+vader+pattern"
        else:
            # Graceful degradation: VADER 40%, patterns 60%
            truth_score = vader_score * 0.40 + pattern_score * 0.60
            method = "vader+pattern (transformer unavailable)"

        truth_score = round(max(0.0, min(100.0, truth_score)), 2)

        # 3. Determine signal details for reasoning
        text_lower = text.lower()
        rumour_hits = sum(1 for p in self.RUMOUR_PATTERNS if re.search(p, text_lower))
        credible_hits = sum(1 for p in self.CREDIBLE_PHRASES if re.search(p, text_lower))
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        exclamation_cnt = text.count("!")

        # 4. Verdict
        if truth_score >= 65:
            verdict = "True"
            reason = "The claim uses measured, credible language with no significant misinformation signals."
            if credible_hits:
                reason = "The claim references credible sources or established scientific language."
        elif truth_score >= 40:
            verdict = "Uncertain"
            reason = "The claim shows mixed signals — some credible markers alongside emotional or unverified language."
        else:
            parts = []
            if rumour_hits > 0:
                parts.append("known conspiracy or misinformation phrases")
            if vader_score < 35:
                parts.append("highly fear-inducing or negative sentiment")
            if caps_ratio > 0.3 or exclamation_cnt >= 2:
                parts.append("excessive capitalisation or exclamation marks")
            if credible_hits == 0:
                parts.append("no credible sourcing detected")
            if transformer_score is not None and transformer_score < 40:
                parts.append("AI model classified this as likely misinformation")
            verdict = "Likely False"
            reason = "Misinformation signals detected: " + (", ".join(parts) or "low credibility score") + "."

        # 5. Confidence (how certain we are about the verdict)
        total_signals = (
            rumour_hits + credible_hits
            + (1 if caps_ratio > 0.3 else 0)
            + (1 if exclamation_cnt >= 2 else 0)
        )
        confidence = min(95, 50 + total_signals * 8)
        # Boost confidence when the transformer strongly agrees
        if transformer_score is not None:
            if truth_score > 80 or truth_score < 20:
                confidence = min(95, confidence + 15)
            elif truth_score > 65 or truth_score < 35:
                confidence = min(95, confidence + 8)
        elif truth_score > 85 or truth_score < 15:
            confidence = min(95, confidence + 10)

        return {
            "score": round(truth_score),
            "verdict": verdict,
            "reason": reason,
            "confidence": confidence,
            "_method": method,   # debug field, not exposed in API schema
        }
