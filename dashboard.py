"""Build a self-contained dashboard.html from the data + results.

Reads golden.jsonl, results/judge_*.jsonl, results/bias.json and
results/reliability.json (whichever exist), computes summary stats, and writes a
single HTML file with all data embedded inline — no server, no CDN, no internet.
Open it by double-clicking.

Run:  python -m harness.runner dashboard
  or: python scripts/build_dashboard.py
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from harness import io
from harness.cost import summarize
from harness.scorer import system_score

ROOT = io.ROOT
RESULTS = io.RESULTS


def _load_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _labels_source() -> str:
    if (io.DATA / "human_labels.jsonl").exists():
        return "real"
    if (io.DATA / "human_labels.example.jsonl").exists():
        return "synthetic (example)"
    return "none"


def build_payload() -> dict:
    golden = _load_jsonl(io.DATA / "golden.jsonl")
    dev_rows = _load_jsonl(RESULTS / "judge_dev.jsonl")
    test_rows = _load_jsonl(RESULTS / "judge_test.jsonl")
    all_rows = dev_rows + test_rows

    # dataset composition
    dataset = {
        "total": len(golden),
        "topics": dict(Counter(i["topic"] for i in golden)),
        "kinds": dict(Counter(i["candidate_kind"] for i in golden)),
        "splits": dict(Counter(i["split"] for i in golden)),
        "difficulty": dict(Counter(i.get("difficulty", "?") for i in golden)),
    }

    # judge verdicts per split (reuse the scorer on the stored verdict dicts)
    def score(rows):
        from harness.schema import JudgeVerdict
        vs = [JudgeVerdict.model_validate(r["verdict"]) for r in rows]
        return system_score(vs) if vs else {"n": 0}

    judge = {"dev": score(dev_rows), "test": score(test_rows), "all": score(all_rows)}

    # cost from judged rows (judge side)
    import os
    cost = None
    if all_rows:
        model = os.getenv("JUDGE_MODEL", "claude-sonnet-5")
        try:
            cr = summarize(model,
                           [r.get("input_tokens", 0) for r in all_rows],
                           [r.get("output_tokens", 0) for r in all_rows],
                           [r.get("latency_ms", 0.0) for r in all_rows])
            cost = cr.as_dict()
        except Exception as e:
            cost = {"error": str(e)}

    reliability = None
    rp = RESULTS / "reliability.json"
    if rp.exists():
        reliability = json.loads(rp.read_text(encoding="utf-8"))

    bias = None
    bp = RESULTS / "bias.json"
    if bp.exists():
        b = json.loads(bp.read_text(encoding="utf-8"))
        # drop the big per-row arrays for the payload
        for k in ("position_bias", "verbosity_bias"):
            if k in b and isinstance(b[k], dict):
                b[k] = {kk: vv for kk, vv in b[k].items() if kk != "rows"}
        bias = b

    items = [{
        "id": r["id"], "topic": r["topic"], "kind": r["candidate_kind"],
        "split": r["split"], "input": r["input"], "output": r["output"],
        "verdict": r["verdict"],
    } for r in all_rows]

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "labels_source": _labels_source(),
        "has_results": bool(all_rows),
        "dataset": dataset,
        "judge": judge,
        "reliability": reliability,
        "bias": bias,
        "cost": cost,
        "items": items,
    }


def build(out_path: Path | str = ROOT / "dashboard.html") -> Path:
    payload = build_payload()
    html = _TEMPLATE.replace("/*__DATA__*/null", json.dumps(payload))
    out = Path(out_path)
    out.write_text(html, encoding="utf-8")
    return out


# The template is one self-contained HTML file. Data is injected where the
# placeholder `/*__DATA__*/null` sits. All rendering is vanilla JS + CSS; charts
# are simple CSS/SVG bars so nothing loads from the network.
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CyberSec AI Grader — Dashboard</title>
<style>
  :root{
    --bg:#0f1420; --panel:#171e2e; --panel2:#1e2740; --ink:#e8edf6; --muted:#93a0b8;
    --line:#2a3550; --accent:#5b8cff; --good:#3ecf8e; --warn:#ffb020; --bad:#ff5c6c;
    --chip:#243050;
  }
  @media (prefers-color-scheme: light){
    :root{ --bg:#f5f7fb; --panel:#ffffff; --panel2:#f0f3fa; --ink:#141a26; --muted:#5a6782;
           --line:#e2e8f2; --accent:#2f6bff; --good:#12a56b; --warn:#b7791f; --bad:#d33f4f; --chip:#eef2fb; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
  header{padding:24px 20px 8px;max-width:1100px;margin:0 auto;}
  h1{font-size:22px;margin:0 0 4px;letter-spacing:.2px}
  h2{font-size:15px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0 0 12px}
  main{max-width:1100px;margin:0 auto;padding:8px 20px 60px;}
  .sub{color:var(--muted);font-size:13px}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 18px 20px;margin:16px 0}
  .grid{display:grid;gap:16px}
  .cards{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}
  .stat{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:14px}
  .stat .n{font-size:26px;font-weight:700}
  .stat .l{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
  .two{grid-template-columns:1fr 1fr}
  @media(max-width:760px){.two{grid-template-columns:1fr}}
  .bar{display:flex;align-items:center;gap:10px;margin:6px 0}
  .bar .lab{width:130px;font-size:13px;color:var(--muted);text-align:right;flex:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .bar .track{flex:1;background:var(--panel2);border-radius:6px;height:16px;overflow:hidden;border:1px solid var(--line)}
  .bar .fill{height:100%;background:var(--accent)}
  .bar .val{width:44px;font-variant-numeric:tabular-nums;font-size:13px}
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
  .chip{display:inline-block;padding:2px 8px;border-radius:999px;background:var(--chip);font-size:12px}
  .pass{color:var(--good)} .fail{color:var(--bad)}
  .pill{padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600}
  .pill.pass{background:color-mix(in srgb,var(--good) 18%,transparent)}
  .pill.fail{background:color-mix(in srgb,var(--bad) 18%,transparent)}
  .kbad{color:var(--bad)} .kmid{color:var(--warn)} .kgood{color:var(--good)}
  .tabs{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap}
  .tab{padding:6px 12px;border:1px solid var(--line);border-radius:999px;cursor:pointer;font-size:13px;background:var(--panel2)}
  .tab.active{background:var(--accent);color:#fff;border-color:transparent}
  input[type=search]{width:100%;padding:9px 12px;border-radius:10px;border:1px solid var(--line);
    background:var(--panel2);color:var(--ink);margin-bottom:10px}
  select{padding:8px 10px;border-radius:10px;border:1px solid var(--line);background:var(--panel2);color:var(--ink)}
  .banner{border-radius:12px;padding:12px 14px;margin:16px 0;font-size:14px;border:1px solid}
  .banner.warn{background:color-mix(in srgb,var(--warn) 12%,transparent);border-color:var(--warn)}
  .banner.info{background:color-mix(in srgb,var(--accent) 12%,transparent);border-color:var(--accent)}
  details{border-top:1px dashed var(--line);padding:6px 0}
  details summary{cursor:pointer;list-style:none}
  details .body{margin:8px 0 4px;color:var(--muted);white-space:pre-wrap}
  .muted{color:var(--muted)}
  .row-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
  code{background:var(--panel2);padding:1px 6px;border-radius:6px}
  .empty{color:var(--muted);padding:14px;text-align:center}
</style>
</head>
<body>
<header>
  <h1>CyberSec AI Grader — Dashboard</h1>
  <div class="sub" id="meta"></div>
</header>
<main id="app"></main>

<script id="payload" type="application/json">/*__DATA__*/null</script>
<script>
const D = JSON.parse(document.getElementById('payload').textContent);
const app = document.getElementById('app');
const el = (t, a={}, ...kids) => { const n=document.createElement(t);
  for(const[k,v] of Object.entries(a)){ if(k==='class')n.className=v; else if(k==='html')n.innerHTML=v; else n.setAttribute(k,v);}
  for(const c of kids){ if(c==null)continue; n.append(c.nodeType?c:document.createTextNode(c)); } return n; };
const pct = (x)=> (x*100).toFixed(1)+'%';
const kcls = (k)=> k==null?'' : k<0.4?'kbad':k<0.6?'kmid':'kgood';

document.getElementById('meta').textContent =
  `Generated ${D.generated_at} · human labels: ${D.labels_source} · ${D.has_results? 'judge results loaded':'no judge results yet'}`;

/* ---- banners ---- */
if(D.labels_source==='synthetic (example)')
  app.append(el('div',{class:'banner warn',html:
    '⚠️ <b>Reliability panel uses SYNTHETIC example labels</b> — for testing the dashboard only. '+
    'Do the real two-labeller pass into <code>data/human_labels.jsonl</code>, then rebuild. Do not report these numbers.'}));
if(D.labels_source==='none')
  app.append(el('div',{class:'banner info',html:
    'ℹ️ No human labels yet — the reliability panel will fill in once you create <code>data/human_labels.jsonl</code> and re-run <code>reliability</code>.'}));
if(!D.has_results)
  app.append(el('div',{class:'banner info',html:
    'ℹ️ No judge results yet — run <code>python -m harness.runner all</code>, then rebuild the dashboard.'}));

/* ---- helper: bar chart from {label:count} ---- */
function barChart(obj, {sort=true, color='var(--accent)'}={}){
  const wrap = el('div');
  let entries = Object.entries(obj);
  if(sort) entries.sort((a,b)=>b[1]-a[1]);
  const max = Math.max(1,...entries.map(e=>e[1]));
  for(const [k,v] of entries){
    wrap.append(el('div',{class:'bar'},
      el('div',{class:'lab'},k),
      el('div',{class:'track'}, el('div',{class:'fill',style:`width:${(v/max*100).toFixed(1)}%;background:${color}`})),
      el('div',{class:'val'}, String(v))));
  }
  return wrap;
}

/* ---- panel: dataset ---- */
function datasetPanel(){
  const d = D.dataset;
  const p = el('section',{class:'panel'}, el('h2',{},'Golden set'));
  const cards = el('div',{class:'grid cards'});
  cards.append(
    stat(d.total,'items'),
    stat(Object.keys(d.topics).length,'topics'),
    stat(d.splits.dev||0,'dev'),
    stat(d.splits.test||0,'test'));
  p.append(cards);
  const two = el('div',{class:'grid two',style:'margin-top:14px'});
  two.append(
    el('div',{}, el('h2',{},'By topic'), barChart(d.topics)),
    el('div',{}, el('h2',{},'By answer kind'), barChart(d.kinds,{color:'var(--warn)'})));
  p.append(two);
  return p;
}
function stat(n,l){ return el('div',{class:'stat'}, el('div',{class:'n'},String(n)), el('div',{class:'l'},l)); }

/* ---- panel: judge verdicts (tabbed by split) ---- */
function judgePanel(){
  const p = el('section',{class:'panel'}, el('h2',{},'Judge verdicts'));
  if(!D.has_results){ p.append(el('div',{class:'empty'},'Run the judge to populate this.')); return p; }
  const tabsRow = el('div',{class:'tabs'});
  const body = el('div');
  const splits=['all','dev','test'];
  splits.forEach((s,i)=>{
    const t=el('div',{class:'tab'+(i===0?' active':'')}, s);
    t.onclick=()=>{ [...tabsRow.children].forEach(c=>c.classList.remove('active')); t.classList.add('active'); render(s); };
    tabsRow.append(t);
  });
  function render(s){
    body.innerHTML='';
    const sc=D.judge[s]; if(!sc||!sc.n){ body.append(el('div',{class:'empty'},'no rows')); return; }
    const cards=el('div',{class:'grid cards'});
    cards.append(stat(sc.n,'graded'), stat(pct(sc.pass_rate),'pass rate'),
                 stat((sc.safety&&sc.safety.fail)||0,'safety fails'));
    body.append(cards);
    const two=el('div',{class:'grid two',style:'margin-top:14px'});
    ['accuracy','completeness','helpfulness'].forEach(f=>{
      if(sc[f]) two.append(el('div',{}, el('h2',{},f), barChart(sc[f],{sort:false,color:'var(--accent)'})));
    });
    body.append(two);
  }
  render('all');
  p.append(tabsRow, body);
  return p;
}

/* ---- panel: reliability ---- */
function agreementTable(block){
  const t=el('table'); t.append(el('tr',{},...['criterion','raw','kappa','label','n'].map(h=>el('th',{},h))));
  for(const [f,v] of Object.entries(block.per_field||{})){
    t.append(el('tr',{},
      el('td',{},f),
      el('td',{}, v.raw!=null?pct(v.raw):'—'),
      el('td',{class:kcls(v.kappa)}, v.kappa!=null?v.kappa.toFixed(3):'—'),
      el('td',{class:'muted'}, v.kappa_label||''),
      el('td',{class:'muted'}, String(v.n ?? (v.dropped!=null?(v.n):'')))));
  }
  return t;
}
function reliabilityPanel(){
  const p=el('section',{class:'panel'}, el('h2',{},'Reliability'));
  if(!D.reliability){ p.append(el('div',{class:'empty'},'No reliability report yet. Add human labels and run the reliability command.')); return p; }
  const two=el('div',{class:'grid two'});
  if(D.reliability.inter_annotator)
    two.append(el('div',{}, el('h2',{},'Human ↔ human'), agreementTable(D.reliability.inter_annotator)));
  if(D.reliability.judge_vs_human)
    two.append(el('div',{}, el('h2',{},'Judge ↔ human'), agreementTable(D.reliability.judge_vs_human)));
  p.append(two);
  p.append(el('div',{class:'sub',style:'margin-top:10px'},
    'Kappa colour: red < 0.4 (fair/slight), amber 0.4–0.6 (moderate), green ≥ 0.6 (substantial+).'));
  return p;
}

/* ---- panel: bias ---- */
function biasPanel(){
  const p=el('section',{class:'panel'}, el('h2',{},'Judge bias checks'));
  if(!D.bias){ p.append(el('div',{class:'empty'},'Run the bias command to populate this.')); return p; }
  const two=el('div',{class:'grid two'});
  const pos=D.bias.position_bias, ver=D.bias.verbosity_bias;
  if(pos) two.append(el('div',{class:'stat'},
    el('h2',{},'Position bias'),
    el('div',{class:'bar'}, el('div',{class:'lab'},'flip rate'), el('div',{class:'track'},
      el('div',{class:'fill',style:`width:${(pos.flip_rate*100).toFixed(1)}%;background:${pos.flip_rate>0.1?'var(--bad)':'var(--good)'}`})), el('div',{class:'val'},pct(pos.flip_rate))),
    el('div',{class:'bar'}, el('div',{class:'lab'},'slot-A pref'), el('div',{class:'track'},
      el('div',{class:'fill',style:`width:${((pos.slot_A_preference??0.5)*100).toFixed(1)}%`})), el('div',{class:'val'}, pos.slot_A_preference!=null?pct(pos.slot_A_preference):'—')),
    el('div',{class:'sub'},`${pos.n_pairs} pairs · ideal: flip rate 0%, slot-A pref 50%`)));
  if(ver) two.append(el('div',{class:'stat'},
    el('h2',{},'Verbosity bias'),
    el('div',{class:'bar'}, el('div',{class:'lab'},'grade ↑ on pad'), el('div',{class:'track'},
      el('div',{class:'fill',style:`width:${(ver.grade_improved_rate*100).toFixed(1)}%;background:${ver.grade_improved_rate>0.1?'var(--bad)':'var(--good)'}`})), el('div',{class:'val'},pct(ver.grade_improved_rate))),
    el('div',{class:'bar'}, el('div',{class:'lab'},'fail→pass'), el('div',{class:'track'},
      el('div',{class:'fill',style:`width:${(ver.verdict_fail_to_pass_rate*100).toFixed(1)}%;background:var(--bad)`})), el('div',{class:'val'},pct(ver.verdict_fail_to_pass_rate))),
    el('div',{class:'sub'},`${ver.n_items} items · ideal: both 0% (padding shouldn't raise the grade)`)));
  p.append(two);
  return p;
}

/* ---- panel: cost ---- */
function costPanel(){
  const p=el('section',{class:'panel'}, el('h2',{},'Cost & latency (judge)'));
  const c=D.cost;
  if(!c || c.error){ p.append(el('div',{class:'empty'}, c&&c.error?('cost unavailable: '+c.error):'No results yet.')); return p; }
  const cards=el('div',{class:'grid cards'});
  cards.append(
    stat('$'+c.cost_per_1k,'per 1k'),
    stat('$'+c.cost_at_100x,'1k @ 100×'),
    stat(c.p50_latency_ms+'ms','p50'),
    stat(c.p95_latency_ms+'ms','p95'));
  p.append(cards);
  p.append(el('div',{class:'sub',style:'margin-top:10px'},
    `model ${c.model} · avg ${c.avg_input_tokens} in / ${c.avg_output_tokens} out tokens · $${c.cost_per_item}/item`));
  return p;
}

/* ---- panel: per-item explorer ---- */
function itemsPanel(){
  const p=el('section',{class:'panel'}, el('h2',{},'Per-item results'));
  if(!D.items.length){ p.append(el('div',{class:'empty'},'No judged items yet.')); return p; }
  const ctr=el('div',{class:'row-controls'});
  const search=el('input',{type:'search',placeholder:'search question / answer / id…'});
  const kindSel=el('select'); kindSel.append(el('option',{value:''},'all kinds'));
  [...new Set(D.items.map(i=>i.kind))].forEach(k=>kindSel.append(el('option',{value:k},k)));
  const verSel=el('select'); ['','pass','fail'].forEach(v=>verSel.append(el('option',{value:v}, v||'all verdicts')));
  ctr.append(search,kindSel,verSel);
  const list=el('div');
  function draw(){
    list.innerHTML='';
    const q=search.value.toLowerCase(), k=kindSel.value, vv=verSel.value;
    const rows=D.items.filter(i=>
      (!k||i.kind===k) && (!vv||i.verdict.verdict===vv) &&
      (!q || (i.input+i.output+i.id).toLowerCase().includes(q)));
    list.append(el('div',{class:'sub',style:'margin:4px 0 8px'}, `${rows.length} shown`));
    for(const i of rows){
      const v=i.verdict;
      const d=el('details');
      d.append(el('summary',{},
        el('span',{class:'pill '+v.verdict}, v.verdict.toUpperCase()), ' ',
        el('span',{class:'chip'}, i.kind), ' ',
        el('span',{class:'muted'}, i.id+' · '+i.topic+' · '+i.split), '  ',
        el('span',{}, i.input.slice(0,70)+(i.input.length>70?'…':''))));
      const body=el('div',{class:'body'});
      body.append(el('div',{html:`<b>Q:</b> ${escapeHtml(i.input)}`}));
      body.append(el('div',{html:`<b>A:</b> ${escapeHtml(i.output)}`,style:'margin-top:6px'}));
      body.append(el('div',{style:'margin-top:8px'},
        chip('safety',v.safety), chip('accuracy',v.accuracy),
        chip('completeness',v.completeness), chip('helpfulness',v.helpfulness)));
      if(v.reason) body.append(el('div',{class:'muted',style:'margin-top:6px'}, '“'+v.reason+'”'));
      d.append(body);
      list.append(d);
    }
  }
  search.oninput=draw; kindSel.onchange=draw; verSel.onchange=draw; draw();
  p.append(ctr,list);
  return p;
}
function chip(label,val){ const cls=val==='pass'||val==='good'?'pass':val==='fail'||val==='bad'?'fail':'';
  return el('span',{class:'chip',style:'margin-right:6px'}, label+': ', el('span',{class:cls}, val)); }
function escapeHtml(s){ return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

app.append(datasetPanel(), judgePanel(), reliabilityPanel(), biasPanel(), costPanel(), itemsPanel());
</script>
</body>
</html>
"""


if __name__ == "__main__":
    out = build()
    print(f"wrote {out.relative_to(ROOT)}")
