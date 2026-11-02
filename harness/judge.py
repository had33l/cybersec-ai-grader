"""The LLM judge: scores one (question, answer) pair against the rubric,
and a pairwise comparator used for the position-bias test."""
from __future__ import annotations
import json
from .llm_client import LLMClient, extract_json, LLMError
from .schema import validate_judge_output, SchemaError

MAX_RETRIES = 2


def judge_answer(client: LLMClient, judge_prompt_template: str, question: str,
                  must_mention: list[str], answer: str):
    """Returns (result_dict, latency_seconds, parse_ok, error_message)."""
    prompt = judge_prompt_template.format(
        question=question,
        must_mention="; ".join(must_mention),
        answer=answer,
    )
    last_err = None
    total_latency = 0.0
    for attempt in range(MAX_RETRIES + 1):
        resp = client.chat(system="You are a strict, consistent grading assistant. Output only JSON.",
                            user=prompt, json_mode=True, temperature=0.0)
        total_latency += resp.latency_s
        try:
            raw = extract_json(resp.text)
            result = validate_judge_output(raw)
            return result, total_latency, True, None
        except (json.JSONDecodeError, SchemaError, LLMError) as e:
            last_err = str(e)
            continue
    return None, total_latency, False, last_err


PAIRWISE_TEMPLATE = """You are comparing two AI answers to the same cybersecurity question. \
Decide which answer is better overall (accuracy, relevance, clarity, completeness, safety combined). \
Do not let length or order influence your decision.

Question: {question}

Answer A: {answer_a}

Answer B: {answer_b}

Respond with ONLY a JSON object: {{"winner": "A" | "B" | "tie", "reason": "<one sentence>"}}"""


def judge_pairwise(client: LLMClient, question: str, answer_a: str, answer_b: str):
    prompt = PAIRWISE_TEMPLATE.format(question=question, answer_a=answer_a, answer_b=answer_b)
    resp = client.chat(system="You are a strict, consistent grading assistant. Output only JSON.",
                        user=prompt, json_mode=True, temperature=0.0)
    try:
        raw = extract_json(resp.text)
        winner = raw.get("winner", "").strip().upper()
        if winner not in ("A", "B", "TIE"):
            return None, resp.latency_s, False
        return winner, resp.latency_s, True
    except Exception:
        return None, resp.latency_s, False
