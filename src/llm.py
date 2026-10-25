"""Shared Gemini client and model name for the nodes that call Gemini."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from google import genai

MODEL = "gemini-3.8-flash"

load_dotenv()


@lru_cache(maxsize=1)
def client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])
