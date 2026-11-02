#!/usr/bin/env python3
"""Fills the generated sections of README.md and postmortem.md from results/summary.json
and results/bias_report.json. Every number comes from those files; interpretive sentences are chosen by
simple thresholds and always shown next to the counts. Re-run any time (idempotent).

  python3 -m harness.finalize ... && python3 fill_docs.py
"""
import json, re, sys
from pathlib import Path

S = json.load(open("results/summary.json"))
BP = Path("results/bias_report.json")
BIAS = json.load(open(BP)) if BP.exists() else None


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def ag(d):
    return (f"exact {d['exact']}/{d['n']} ({d['exact_pct']}%), within 1 point {d['within1']}/{d['n']} "
            f"({d['within1_pct']}%), Cohen's kappa {d['kappa']}")


def confusion(jvh):
    c = {}
    for k, v in jvh["confusion_human_consensus_vs_judge"].items():
        h, j = re.match(r"human=(\d),judge=(\d)", k).groups()
        c[(int(h), int(j))] = v
    return c


def runs():
    t = next(((p, r) for p, r in S["runs"].items() if "test" in p and r), (None, None))
    d = next(((p, r) for p, r in S["runs"].items() if "dev" in p and r), (None, None))
    return t, d


def run_line(name, pr):
    p, r = pr
    if not r:
        return f"- {name}: NOT MEASURED"
    oc = r["overall_counts"]
    return (f"- {name} ({p}): mean overall **{r['mean_overall']} / 5** over {r['scored']}/{r['items']} items; "
            f"overall 1/2/3/4/5 = {oc['1']}/{oc['2']}/{oc['3']}/{oc['4']}/{oc['5']} "
            f"({r['overall_pct']['5']}% scored 5); {r['unsafe']} flagged unsafe; {r['failures']} failures.")


def bias_lines():
    if not BIAS:
        return ["- Position / verbosity bias: **NOT YET MEASURED** (run `harness/bias_tests.py`)."]
    p, v = BIAS["position_bias"], BIAS["verbosity_bias"]
    out = []
    if p.get("pairs_tested"):
        fr, fs = p["flip_rate"], p["first_slot_rate"]
        size = "large" if fr >= 0.25 else "moderate" if fr >= 0.10 else "small"
        slot = ("favours the answer shown FIRST" if fs > 0.6 else "favours the answer shown SECOND" if fs < 0.4
                else "shows no clear preference for either slot")
        out.append(f"- **Position bias** (system answer vs the expert reference, both orders, n={p['pairs_tested']} pairs): "
                   f"{p['flipped']} of {p['pairs_tested']} verdicts changed when the order was swapped ({pct(p['flipped'], p['pairs_tested'])}, "
                   f"a {size} flip rate); {p['consistent']} were consistent. The judge picked the first slot in "
                   f"{p['picked_first_slot']}/{p['total_verdicts']} verdicts ({pct(p['picked_first_slot'], p['total_verdicts'])}), i.e. it {slot}. "
                   f"{p['skipped_unparseable']} pairs were skipped (unparseable or LLM errors).")
    else:
        out.append(f"- **Position bias**: 0 pairs tested ({p.get('note', '')}).")
    if v.get("items_tested"):
        det = v["details"]
        elig = [x for x in det if x["original_score"] < 5]
        rose_e = sum(x["delta"] > 0 for x in elig)
        at5 = len(det) - len(elig)
        out.append(f"- **Verbosity bias** (same answer + one filler sentence, n={v['items_tested']}): score rose on {v['score_rose']}, "
                   f"unchanged on {v['score_unchanged']}, dropped on {v['score_dropped']}. {at5} of the {v['items_tested']} items already "
                   f"scored 5 and could not rise, so the fairer figure is **{rose_e} of {len(elig)} items below 5 ({pct(rose_e, len(elig))}) rose**. "
                   + ("That is a sign of verbosity sensitivity." if elig and rose_e / len(elig) >= 0.3 else
                      "No strong verbosity effect was detected, but the test is weak because of the ceiling effect."))
    else:
        out.append("- **Verbosity bias**: 0 items tested.")
    return out


def results_block():
    L, J = S["labels"], S["judge_vs_human"]
    (tp, td) = runs()
    o = ["_(generated from results/summary.json and results/bias_report.json by `fill_docs.py`)_", ""]
    o += ["**System score (v1, phi3:mini answers, gemma2:9b judge)**", run_line("Test set", tp), run_line("Dev set", td), ""]
    if L:
        h = L["human_human"]
        o += ["**Human labels**",
              f"- Two labellers scored {L['labelled_by_both']} items each; {L['dropped_by_either']} dropped.",
              f"- Human vs human: {ag(h)}; mean difference {h['mean_signed_diff_a_minus_b']} ({L['labellers'][0]} minus {L['labellers'][1]}); "
              f"{L['disagreements_2plus']} items ({pct(L['disagreements_2plus'], h['n'])}) differed by 2+ points (listed in results/dropped_items.md).", ""]
    if J:
        o += ["**Judge vs humans**"]
        for k, v in J.items():
            if k.startswith("judge_vs"):
                o.append(f"- {k.replace('_', ' ')} (n={v['n']}): {ag(v)}; judge minus human on average {v['mean_signed_diff_a_minus_b']:+}.")
        o.append("")
    o += ["**Judge bias**"] + bias_lines() + [""]
    c = S.get("cost")
    if c:
        m, l, k = c["mean_tokens"], c["latency_s"], c["per_1k_requests_usd"]
        key = next(iter(c["at_scale_usd"]))
        o += ["**Cost** (measured tokens/latency; prices are assumptions in `cost_assumptions.json`)",
              f"- Mean tokens/item: generation {m['gen_in']} in / {m['gen_out']} out; judge {m['judge_in']} in / {m['judge_out']} out.",
              f"- Latency (CPU-only laptop): generation median {l['gen_median']}s, judge median {l['judge_median']}s.",
              f"- Per 1k requests: hosted small model ${k['hosted_production']} (answer only) / ${k['hosted_eval']} (answer+judge); "
              f"local machine ${k['local_production']} / ${k['local_eval']}.",
              f"- At 100x ({key}): hosted ${c['at_scale_usd'][key]['hosted_production']}, local ${c['at_scale_usd'][key]['local_production']}; "
              f"serving that volume sequentially on this laptop would take about {c['sequential_local_serving_days_for_scaled_volume']} days."]
    return "\n".join(o)


def judge_block():
    J = S["judge_vs_human"]
    if not J:
        return "NOT YET MEASURED (no human labels)."
    c = confusion(J)
    low = sum(v for (h, j), v in c.items() if h <= 3)
    low_missed = sum(v for (h, j), v in c.items() if h <= 3 and j >= 4)
    high = sum(v for (h, j), v in c.items() if h >= 4)
    high_pen = sum(v for (h, j), v in c.items() if h >= 4 and j < 4)
    h4 = sum(v for (h, j), v in c.items() if h == 4)
    h4j5 = c.get((4, 5), 0)
    jlow = sum(v for (h, j), v in c.items() if j <= 3)
    jlow_ok = sum(v for (h, j), v in c.items() if j <= 3 and h <= 3)
    cons = J["judge_vs_consensus(rounded mean)"]
    o = [f"All figures below use the {cons['n']} items on which the two humans differed by at most 1 point (their rounded mean is the "
         "'consensus'); the items they disagreed on by 2+ points are excluded, which flatters the judge.", "",
         f"- **It is lenient.** On average it scores {cons['mean_signed_diff_a_minus_b']:+} points above the consensus "
         f"(and {J[[k for k in J if k.startswith('judge_vs_') and 'consensus' not in k][0]]['mean_signed_diff_a_minus_b']:+} / "
         f"{J[[k for k in J if k.startswith('judge_vs_') and 'consensus' not in k][1]]['mean_signed_diff_a_minus_b']:+} above the two individual labellers).",
         f"- **It misses weak answers.** Humans rated {low} answers 3 or lower; the judge gave {low_missed} of them a 4 or 5 ({pct(low_missed, low)}).",
         f"- **It rarely marks down good answers.** Humans rated {high} answers 4 or 5; the judge scored only {high_pen} of them below 4 ({pct(high_pen, high)}).",
         f"- **Most disagreement is 4 vs 5.** Humans gave {h4} answers a 4; the judge gave a 5 to {h4j5} of those ({pct(h4j5, h4)}). "
         "A 5 from this judge therefore carries little information.",
         f"- **When it does flag low, it is usually right.** It scored {jlow} answers 3 or lower; the humans agreed on {jlow_ok} ({pct(jlow_ok, jlow)}) - "
         "but it flags very few, so recall is poor.",
         f"- **Agreement statistics are depressed by the ceiling effect.** Exact agreement with the consensus is {cons['exact_pct']}% and kappa is "
         f"{cons['kappa']}, partly because almost all scores sit at 4-5; read kappa together with the counts, never alone."]
    if BIAS:
        o += ["", "Bias results (see Results in the README): " + " ".join(l.lstrip("- ").replace("**", "") for l in bias_lines())]
    o += ["", "What we have NOT tested: whether the judge can be gamed by adversarial answers (e.g. confident but wrong text that happens to echo the rubric), "
          "and whether stricter rubric anchors or few-shot examples would fix the leniency. Both are obvious next experiments."]
    return "\n".join(o)


def fill(path, tag, text):
    s = Path(path).read_text()
    pat = re.compile(rf"(<!--AUTO:{tag}-->)(.*?)(<!--/AUTO:{tag}-->)", re.S)
    if not pat.search(s):
        sys.exit(f"{path}: marker AUTO:{tag} not found")
    Path(path).write_text(pat.sub(lambda m: f"{m.group(1)}\n{text}\n{m.group(3)}", s))
    print(f"filled {tag} in {path}")


fill("README.md", "RESULTS", results_block())
fill("postmortem.md", "JUDGE", judge_block())
