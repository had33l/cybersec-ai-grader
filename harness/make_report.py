#!/usr/bin/env python3
"""Builds report.pdf (max 4 pages) from results/summary.json.
Anything missing from the summary is printed as NOT YET MEASURED - never invented.

Usage: python3 -m harness.make_report [--summary results/summary.json] [--out report.pdf]
Optional team.json: {"team": "Name1, Name2", "course": "...", "task_note": "..."}
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NM = '<font color="#b00020"><b>NOT YET MEASURED</b></font>'
ss = getSampleStyleSheet()
B = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.6, leading=11, spaceAfter=3)
H = ParagraphStyle("h", parent=ss["Heading2"], fontSize=11, spaceBefore=6, spaceAfter=3, textColor=colors.HexColor("#1f4e79"))
T = ParagraphStyle("t", parent=ss["Title"], fontSize=16, spaceAfter=2)
S = ParagraphStyle("s", parent=B, fontSize=7.5, leading=9)


def tbl(data, widths=None):
    t = Table([[Paragraph(str(c), S) for c in r] for r in data], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe8f3")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return t


def ag(d):
    return NM if not d else (f"n={d['n']}: exact {d['exact']}/{d['n']} ({d['exact_pct']}%), within-1 {d['within1']}/{d['n']} "
                             f"({d['within1_pct']}%), Cohen's kappa {d['kappa']}, mean signed diff {d['mean_signed_diff_a_minus_b']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="results/summary.json")
    ap.add_argument("--out", default="report.pdf")
    a = ap.parse_args()
    s = json.load(open(a.summary))
    team = json.load(open("team.json")) if Path("team.json").exists() else {}
    st = []
    st += [Paragraph("CyberSec AI Grader - Project 1 report", T),
           Paragraph(f"CS496 AI Engineering, Fall 2026 &nbsp;|&nbsp; Team: {team.get('team', '(add names in team.json)')}", S), Spacer(1, 4)]

    st += [Paragraph("1. The task and why exact match is not enough", H), Paragraph(
        "The system answers practical cybersecurity questions from non-experts (phishing, malware, ransomware, passwords, MFA, "
        "network safety). There is no single correct string: two answers can both be right with different wording, and an answer "
        "that sounds fluent can still be unsafe (e.g. 'just pay the ransom'). Exact match or keyword overlap would score a correct "
        "paraphrase as wrong and a confident, wrong answer as right. A careful person can judge quality on five criteria "
        "(accuracy, relevance, clarity, completeness, safety, each 1-5 plus an overall 1-5) - that rubric fits on two pages "
        "(data/labelling_guide.md) - so this is a task for an LLM judge validated against human labels. One model call per item; "
        "no agents or retrieval.", B)]

    L = s.get("labels")
    st += [Paragraph("2. The golden set", H), Paragraph(
        f"{s['golden_set_size']} questions in data/golden_set.jsonl, split into a dev set (prompt iteration) and a test set "
        "(final numbers only), stored as jsonl. Each item carries an expert-written rubric (must_mention) used for completeness."
        + ((" " + team["labelling_note"]) if (L and team.get("labelling_note")) else
           (" Two labellers labelled every answered item independently and blind to the judge, following the labelling guide; "
            "items where they differed by 2+ points were discussed and re-labelled or dropped (results/dropped_items.md)." if L else "")), B)]
    if L:
        st += [tbl([["Measure", "Value"],
                    ["Items labelled (A / B / both)", f"{L['labelled_by_a']} / {L['labelled_by_b']} / {L['labelled_by_both']}"],
                    ["Dropped by either labeller", f"{L['dropped_by_either']} of {L['labelled_by_both']} ({100*L['dropped_by_either']/max(1,L['labelled_by_both']):.1f}%) - reasons in results/dropped_items.md"],
                    ["Human vs human (overall)", ag(L["human_human"])],
                    ["Differ by 2+ points", f"{L['disagreements_2plus']} items ({100*L['disagreements_2plus']/max(1,L['human_human']['n']):.1f}%)"]],
                   [5 * cm, 12 * cm])]
    else:
        st += [Paragraph(f"Labeller agreement and dropped items: {NM} (needs two label files).", B)]

    st += [Paragraph("3. The harness", H), Paragraph(
        "One command (make run) runs the system on a dataset and writes one row per item to results/*.jsonl: input, answer, five "
        "criterion scores, overall, one-sentence reason, unsafe flag, latency and token counts. A sidecar .meta.json records the "
        "dataset hash, prompt hashes, models and git commit so every run is traceable. The judge is asked for JSON in a fixed schema "
        "(harness/schema.py); invalid output is retried twice and then logged as a parse failure, never guessed. The answering model "
        "and the judge model are separate clients and can be different models. Prompts live in prompts/ under git; "
        "prompts/CHANGELOG.md links each change to its score.", B)]
    runs = s.get("runs", {})
    if runs:
        rows = [["Run file", "Items", "Scored", "Parse/gen failures", "Mean overall", "Overall 1-5 counts (%)", "Unsafe"]]
        for p, r in runs.items():
            if not r or "mean_overall" not in r:
                rows.append([p, r and r["items"], "-", "-", "-", "-", "-"]); continue
            rows.append([p, r["items"], r["scored"], r["failures"], r["mean_overall"],
                         " | ".join(f"{k}:{r['overall_counts'][k]} ({r['overall_pct'][k]}%)" for k in map(str, range(1, 6))), r["unsafe"]])
        st += [tbl(rows, [3.9 * cm, 1.2 * cm, 1.4 * cm, 1.9 * cm, 1.6 * cm, 5.9 * cm, 1.4 * cm])]
    bad = {p: d for p, d in s.get("dataset_consistency", {}).items() if d["mismatched_vs_golden_set"]}
    if bad:
        st += [Paragraph("<b>Warning:</b> " + "; ".join(f"{p}: {d['mismatched_vs_golden_set']}/{d['rows']} rows do not match the golden set" for p, d in bad.items()), B)]

    jh = s.get("judge_vs_human")
    st += [Paragraph("4. The judge: reliability report", H)]
    if jh:
        rows = [["Comparison", "Result"]] + [[k.replace("_", " "), ag(v)] for k, v in jh.items() if k.startswith("judge_vs")]
        st += [tbl(rows, [5 * cm, 12 * cm])]
    else:
        st += [Paragraph(f"Judge vs human agreement: {NM}", B)]
    bias = s.get("bias")
    if bias:
        p, v = bias["position_bias"], bias["verbosity_bias"]
        st += [Paragraph(
            f"<b>Position bias</b> (system answer vs expert reference, both orders): "
            + (f"{p['pairs_tested']} pairs, {p['flipped']} verdicts flipped ({100*p['flip_rate']:.1f}%), {p['consistent']} consistent; "
               f"judge picked the first slot in {p['picked_first_slot']}/{p['total_verdicts']} verdicts ({100*p['first_slot_rate']:.1f}%); "
               f"{p['skipped_unparseable']} skipped." if p.get("pairs_tested") else f"0 pairs tested ({p.get('note','')})")
            + "<br/><b>Verbosity bias</b> (answer padded with content-free filler): "
            + (f"{v['items_tested']} items, score rose on {v['score_rose']} ({100*v['score_rose_rate']:.1f}%), unchanged {v['score_unchanged']}, dropped {v['score_dropped']}."
               if v.get("items_tested") else "0 items tested."), B)]
    else:
        st += [Paragraph(f"Position-bias and verbosity-bias checks: {NM}", B)]
    st += [Paragraph("<b>Where the judge fails</b> and its limits are listed in postmortem.md.", B)]

    st += [Paragraph("5. The system: score history", H)]
    ch = s.get("changelog") or []
    if ch:
        st += [tbl([["Ver.", "Files", "Change", "Test-set avg overall", "Delta"]] + [r[:5] for r in ch], [1.4*cm, 3.6*cm, 6.6*cm, 4*cm, 1.4*cm])]
    else:
        st += [Paragraph(f"No changelog rows: {NM}", B)]

    st += [Paragraph("6. Cost model", H)]
    c = s.get("cost")
    if c and c.get("n"):
        m, l, k, sc = c["mean_tokens"], c["latency_s"], c["per_1k_requests_usd"], c["at_scale_usd"]
        key = next(iter(sc))
        st += [Paragraph(
            f"From {c['n']} answered items{' (token counts ESTIMATED from word counts)' if c['tokens_estimated_from_words'] else ''}: "
            f"mean tokens/item - generation {m['gen_in']} in / {m['gen_out']} out, judge {m['judge_in']} in / {m['judge_out']} out. "
            f"Mean latency - generation {l['gen_mean']}s, judge {l['judge_mean']}s (medians {l['gen_median']}s / {l['judge_median']}s).", B),
            tbl([["USD", "per 1k requests (today)", f"at 100x ({key})"],
                 ["Hosted small model - production (answer only)", k["hosted_production"], sc[key]["hosted_production"]],
                 ["Hosted small model - evaluation (answer+judge)", k["hosted_eval"], "-"],
                 ["Local machine - production", k["local_production"], sc[key]["local_production"]],
                 ["Local machine - evaluation", k["local_eval"], "-"]], [8 * cm, 4.5 * cm, 4.5 * cm]),
            Paragraph(f"Serving 100x volume sequentially on the local model would take about {c['sequential_local_serving_days_for_scaled_volume']} days, "
                      "so local inference does not scale without batching or a hosted/GPU server. Hosted prices and the local hourly cost are "
                      "assumptions in cost_assumptions.json (illustrative - verify against the provider's pricing page).", B)]
    else:
        st += [Paragraph(f"Cost model: {NM} (needs a test-set run).", B)]

    SimpleDocTemplate(a.out, pagesize=A4, leftMargin=1.6*cm, rightMargin=1.6*cm, topMargin=1.4*cm, bottomMargin=1.3*cm,
                      title="Project 1 report").build(st)
    from pypdf import PdfReader
    try:
        n = len(PdfReader(a.out).pages)
        print(f"Wrote {a.out} ({n} pages)" + ("  <-- OVER the 4-page limit!" if n > 4 else ""))
    except Exception:
        print(f"Wrote {a.out}")


if __name__ == "__main__":
    main()
