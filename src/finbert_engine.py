
"""Local FinBERT financial sentiment analysis."""

from functools import lru_cache

import torch
from transformers import AutoTokenizer, pipeline

MODEL_ID = "ProsusAI/finbert"
MAX_LENGTH = 512


@lru_cache(maxsize=1)
def _load_model():
    """Load FinBERT and its tokenizer once, then reuse them."""
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

    classifier = pipeline(
        "text-classification",
        model=MODEL_ID,
        tokenizer=tokenizer,
        top_k=None,
        device=-1,  # Run locally on CPU
    )

    return classifier, tokenizer


def analyze_finbert(text: str) -> dict:
    """
    Classify financial sentiment locally.

    Long inputs are truncated to the model's supported token length.
    The original text is not modified.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text to analyze cannot be empty.")

    classifier, tokenizer = _load_model()

    # Explicitly tokenize with truncation to avoid exceeding
    # FinBERT's positional embedding limit.
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
    )

    # Decode the truncated input so the pipeline receives only
    # the text represented by the tokenized input.
    truncated_text = tokenizer.decode(
        inputs["input_ids"][0],
        skip_special_tokens=True,
    )

    predictions = classifier(truncated_text)[0]

    scores = {
        item["label"].lower(): float(item["score"])
        for item in predictions
    }

    required = {"positive", "negative", "neutral"}
    if not required.issubset(scores):
        raise RuntimeError(
            f"Unexpected FinBERT labels: {list(scores)}"
        )

    return {
        "label": max(scores, key=scores.get),
        "sentiment": scores["positive"] - scores["negative"],
        "scores": scores,
        "model": MODEL_ID,
        "method": "Local FinBERT inference (truncated input)",
    }
