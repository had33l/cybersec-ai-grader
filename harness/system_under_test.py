"""The system being evaluated: given a question, produce a cybersecurity answer."""
from __future__ import annotations
from pathlib import Path
from .llm_client import LLMClient


def load_prompt(path: str) -> str:
    return Path(path).read_text().strip()


def generate_answer(client: LLMClient, system_prompt: str, question: str):
    """Returns (answer_text, latency_seconds)."""
    resp = client.chat(system=system_prompt, user=question, json_mode=False, temperature=0.3)
    return resp.text.strip(), resp.latency_s
