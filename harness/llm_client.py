"""
Minimal LLM client used by both the system-under-test and the judge.

Backends supported:
  - "ollama"  -> local Ollama server (default: http://localhost:11434), any pulled
                 model works, e.g. "qwen2.5:7b", "llama3.1:8b", "mistral".
  - "openai"  -> any OpenAI-compatible chat completions endpoint (OpenAI itself,
                 or a local server like vLLM / LM Studio that speaks the same API).

Set the backend with the LLM_BACKEND env var, or pass --backend on the CLI.
This is the ONLY file that talks to the network. Everything else calls
LLMClient.chat() and gets plain text back.

Memory note: if you're running two different models (one to answer, one to
judge) on a machine that can't hold both in RAM at once, set OLLAMA_KEEP_ALIVE
to a short value (e.g. "5s") so Ollama evicts a model shortly after each call
instead of keeping both resident — trades speed for staying under your RAM
budget. Leave it unset (or "5m"+) if you have enough RAM to keep both loaded,
which is faster.
"""
from __future__ import annotations

import json
import os
import time
import requests
from dataclasses import dataclass


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    text: str
    latency_s: float
    raw: dict


class LLMClient:
    def __init__(
        self,
        backend: str | None = None,
        model: str | None = None,
        host: str | None = None,
        api_key: str | None = None,
        timeout: int = 600,
        keep_alive: str | None = None,
    ):
        self.backend = backend or os.environ.get("LLM_BACKEND", "ollama")
        self.model = model or os.environ.get("LLM_MODEL", "qwen2.5:7b")
        self.timeout = timeout
        # cumulative token usage across all calls made by this client; the
        # runner diffs these per item so every results row carries its tokens
        self.tokens_in = 0
        self.tokens_out = 0
        # Default keep_alive comes from OLLAMA_KEEP_ALIVE env var if set.
        # Passing a short duration (e.g. "5s") stops Ollama from keeping
        # multiple different models loaded in RAM at once when you alternate
        # between an answer-model and a judge-model on a memory-constrained
        # machine — each call unloads shortly after, freeing RAM for the
        # other model's next call. Costs reload time; avoids OOM crashes.
        self.keep_alive = keep_alive if keep_alive is not None else os.environ.get("OLLAMA_KEEP_ALIVE")

        if self.backend == "ollama":
            self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        elif self.backend == "openai":
            self.host = (host or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        else:
            raise LLMError(f"Unknown backend '{self.backend}'. Use 'ollama' or 'openai'.")

    # ------------------------------------------------------------------ #
    def chat(self, system: str, user: str, json_mode: bool = False, temperature: float = 0.2) -> LLMResponse:
        """Send one system+user turn, return the assistant's text."""
        start = time.time()
        if self.backend == "ollama":
            text, raw = self._chat_ollama(system, user, json_mode, temperature)
        else:
            text, raw = self._chat_openai(system, user, json_mode, temperature)
        self._count_tokens(raw)
        return LLMResponse(text=text, latency_s=time.time() - start, raw=raw)

    def _count_tokens(self, raw: dict):
        if self.backend == "ollama":
            self.tokens_in += int(raw.get("prompt_eval_count", 0) or 0)
            self.tokens_out += int(raw.get("eval_count", 0) or 0)
        else:
            u = raw.get("usage", {}) or {}
            self.tokens_in += int(u.get("prompt_tokens", 0) or 0)
            self.tokens_out += int(u.get("completion_tokens", 0) or 0)

    # ------------------------------------------------------------------ #
    def _chat_ollama(self, system, user, json_mode, temperature):
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Could not reach Ollama at {self.host}. This usually means the Ollama "
                f"server process crashed (often from running out of RAM with multiple "
                f"models loaded at once — check `free -h` and `dmesg | grep -i kill`) "
                f"or was never started (`ollama serve`). Is `{self.model}` pulled? "
                f"(ollama pull {self.model}) ({e})"
            )
        if resp.status_code != 200:
            raise LLMError(f"Ollama returned {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return data.get("message", {}).get("content", ""), data

    def _chat_openai(self, system, user, json_mode, temperature):
        url = f"{self.host}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        if resp.status_code != 200:
            raise LLMError(f"OpenAI-compatible endpoint returned {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"], data


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction: strips markdown fences, finds the outer {...}."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(t[start : end + 1])
        raise
