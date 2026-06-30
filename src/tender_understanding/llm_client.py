"""
llm_client.py — Thin wrapper around the configured LLM endpoint (Llama 3.1,
via Ollama-style API by default). Keeping this separate makes it easy to
swap providers later without touching extraction logic.
"""
from __future__ import annotations

import json

import requests

from src.common.config import get_settings


class LLMError(Exception):
    pass


def call_llm(prompt: str, system: str | None = None, json_mode: bool = False) -> str:
    """
    Sends a single prompt to the configured LLM and returns the raw text response.
    Set json_mode=True to instruct the model to return only valid JSON.
    """
    settings = get_settings()
    llm_cfg = settings.get("llm", {})
    endpoint = llm_cfg.get("endpoint", "http://localhost:11434/api")
    model = llm_cfg.get("model", "llama3.1")
    timeout = llm_cfg.get("timeout_seconds", 120)

    payload = {
        "model": model,
        "prompt": prompt,
        "system": system or "",
        "stream": False,
        "format": "json" if json_mode else None,
    }

    try:
        resp = requests.post(f"{endpoint}/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise LLMError(f"LLM request failed: {e}") from e

    data = resp.json()
    return data.get("response", "")


def call_llm_json(prompt: str, system: str | None = None) -> dict:
    """Calls the LLM in JSON mode and parses the result. Raises LLMError on bad JSON."""
    raw = call_llm(prompt, system=system, json_mode=True)
    # Strip markdown code fences if the model added them despite instructions.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM did not return valid JSON: {e}\nRaw response: {raw[:500]}") from e
