"""Cost model: cost per 1k requests today and at 100x, from a real results file.

Two things are costed separately:
  * PRODUCTION cost  = answer generation only (what the system costs to serve a request)
  * EVAL cost        = answer + judge (what it costs to evaluate one item)
Token counts come from the per-row token fields the runner writes. Older result
files without them fall back to a words*1.33 estimate and are flagged as estimated.

Usage: python3 -m harness.cost results/run_test_v1.jsonl [--assumptions cost_assumptions.json]
"""
from __future__ import annotations
import argparse, json, statistics, sys
from pathlib import Path


def _tok(row, key_tokens, text):
    if key_tokens in row and row[key_tokens]:
        return row[key_tokens], False
    return int(len((text or "").split()) * 1.33), True


def cost_model(rows, assumptions):
    rows = [r for r in rows if "answer" in r]
    if not rows:
        return {"n": 0}
    est = False
    g_in, g_out, j_in, j_out, g_lat, j_lat = [], [], [], [], [], []
    for r in rows:
        a, e1 = _tok(r, "gen_tokens_in", r["question"]); b, e2 = _tok(r, "gen_tokens_out", r["answer"])
        c, e3 = _tok(r, "judge_tokens_in", r["question"] + r["answer"]); d, e4 = _tok(r, "judge_tokens_out", r.get("reason", "") + " " * 40)
        est = est or e1 or e2 or e3 or e4
        g_in.append(a); g_out.append(b); j_in.append(c); j_out.append(d)
        g_lat.append(r.get("gen_latency_s", 0)); j_lat.append(r.get("judge_latency_s", 0))
    m = statistics.mean
    unit, scale = assumptions.get("requests_unit", 1000), assumptions.get("scale_factor", 100)
    h = assumptions["hosted_example"]; loc = assumptions["local"]

    def hosted(tin, tout):
        return (tin * h["price_in_per_m"] + tout * h["price_out_per_m"]) / 1e6

    prod_h = hosted(m(g_in), m(g_out)) * unit
    eval_h = hosted(m(g_in) + m(j_in), m(g_out) + m(j_out)) * unit
    prod_lat, eval_lat = m(g_lat), m(g_lat) + m(j_lat)
    prod_l = prod_lat / 3600 * loc["cost_per_hour_usd"] * unit
    eval_l = eval_lat / 3600 * loc["cost_per_hour_usd"] * unit
    return {
        "n": len(rows), "tokens_estimated_from_words": est,
        "mean_tokens": {"gen_in": round(m(g_in), 1), "gen_out": round(m(g_out), 1),
                        "judge_in": round(m(j_in), 1), "judge_out": round(m(j_out), 1)},
        "latency_s": {"gen_mean": round(prod_lat, 2), "gen_median": round(statistics.median(g_lat), 2),
                      "judge_mean": round(m(j_lat), 2), "judge_median": round(statistics.median(j_lat), 2)},
        "per_1k_requests_usd": {"hosted_production": round(prod_h, 4), "hosted_eval": round(eval_h, 4),
                                "local_production": round(prod_l, 4), "local_eval": round(eval_l, 4)},
        "at_scale_usd": {f"{unit*scale} requests": {
            "hosted_production": round(prod_h * scale, 2), "local_production": round(prod_l * scale, 2)}},
        "sequential_local_serving_days_for_scaled_volume": round(prod_lat * unit * scale / 86400, 1),
        "assumptions": assumptions,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--assumptions", default="cost_assumptions.json")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.run) if l.strip()]
    print(json.dumps(cost_model(rows, json.load(open(a.assumptions))), indent=2))


if __name__ == "__main__":
    main()
