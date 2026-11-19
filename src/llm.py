"""Shared Gemini client and model name for the nodes that call Gemini."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from google import genai
from google.genai import types

MODEL = "gemini-3.1-flash-lite"

# A hung or overloaded Gemini call must fail fast: a run makes ~3 sequential calls and the
# Vercel function limit is 100s (vercel.json). Per call: 20s timeout, 2 attempts (one retry);
# the SDK retries 408/429/5xx (e.g. 503 "high demand") with backoff.
REQUEST_TIMEOUT_MS = 20_000
MAX_ATTEMPTS = 2

load_dotenv()


@lru_cache(maxsize=1)
def client() -> genai.Client:
    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=MAX_ATTEMPTS),
        ),
    )
