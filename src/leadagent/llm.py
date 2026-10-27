"""Thin wrapper around the Gemini REST API (free tier). Returns parsed JSON."""
import json
import os
import re
import time

import requests

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is missing. Copy .env.example to .env and add your key.")

    def generate_json(self, system, prompt, retries=4):
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        for attempt in range(retries):
            try:
                resp = requests.post(API_URL.format(model=self.model), headers=headers, json=body, timeout=90)
            except requests.RequestException:   # dropped connection, SSL hiccup, timeout
                time.sleep(5 * (attempt + 1))
                continue
            if resp.status_code == 429 and "PerDay" in resp.text:   # daily free quota: retrying is pointless
                raise LLMError(f"Daily free quota for '{self.model}' is used up. Try another model "
                               "(set GEMINI_MODEL in .env) or wait until tomorrow.")
            if resp.status_code in (429, 500, 503):   # per-minute rate limit / temporary overload
                time.sleep(2 ** (attempt + 1) * 5)
                continue
            if resp.status_code != 200:
                raise LLMError(f"Gemini error {resp.status_code}: {resp.text[:300]}")
            try:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMError(f"Unexpected Gemini response: {resp.text[:300]}") from exc
            return parse_json(text)
        raise LLMError("Gemini is unreachable, rate-limiting or overloaded; wait a minute and retry.")


def parse_json(text):
    """Parse JSON, tolerating a ```json fence around it."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {text[:200]}") from exc
