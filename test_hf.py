from transformers import pipeline

try:
    classifier = pipeline("text-classification", model="distilroberta-base")
    res = classifier("Vaccines are safe.")
    print("distilroberta-base classification result:", res)
except Exception as e:
    print(f"Error: {e}")

try:
    zs = pipeline("zero-shot-classification", model="cross-encoder/nli-distilroberta-base")
    res = zs("Vaccines are safe.", candidate_labels=["True", "False", "Uncertain"])
    print("zero-shot result:", res)
except Exception as e:
    print(f"Error: {e}")
