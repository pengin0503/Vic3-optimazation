#!/usr/bin/env python3
"""Analyze repeated Victoria 3 TickTask benchmark runs."""

from __future__ import annotations
import argparse, csv, json, math, statistics, sys
from pathlib import Path

REQ={"frame","task","milliseconds","calls","longest_lock"}
class Error(RuntimeError): pass

def number(v,name,row):
    try:x=float(v)
    except Exception as e:raise Error(f"row {row}: invalid {name}={v!r}") from e
    if not math.isfinite(x):raise Error(f"row {row}: non-finite {name}")
    return x

def load_manifest(p):
    try:d=json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:raise Error(f"invalid manifest {p}: {e}") from e
    need=("run_id","variant","task_thread_count","wall_clock_seconds","ticktask_csv")
    miss=[k for k in need if k not in d]
    if miss:raise Error(f"{p}: missing {', '.join(miss)}")
    if not isinstance(d["task_thread_count"],int) or d["task_thread_count"]<1:raise Error(f"{p}: bad task_thread_count")
    if not isinstance(d["wall_clock_seconds"],(int,float)) or d["wall_clock_seconds"]<=0:raise Error(f"{p}: bad wall_clock_seconds")
    return d

def load_csv(p):
    try:f=p.open("r",encoding="utf-8-sig",newline="")
    except FileNotFoundError as e:raise Error(f"missing TickTask CSV: {p}") from e
    with f:
        r=csv.DictReader(f); miss=REQ-set(r.fieldnames or ())
        if miss:raise Error(f"{p}: missing CSV columns: {', '.join(sorted(miss))}")
        out={}
        for n,row in enumerate(r,2):
            task=(row["task"] or "").strip()
            if not task:raise Error(f"{p}: row {n}: empty task")
            ms=number(row["milliseconds"],"milliseconds",n); calls=number(row["calls"],"calls",n); lock=number(row["longest_lock"],"longest_lock",n)
            if min(ms,calls,lock)<0 or int(calls)!=calls:raise Error(f"{p}: row {n}: invalid timing/calls")
            a=out.setdefault(task,{"total_ms":0.0,"calls":0,"max_record_ms":0.0,"longest_lock_ms":0.0,"records":0})
            a["total_ms"]+=ms;a["calls"]+=int(calls);a["max_record_ms"]=max(a["max_record_ms"],ms);a["longest_lock_ms"]=max(a["longest_lock_ms"],lock);a["records"]+=1
        return out

def discover(root):
    if root.is_file():return [root]
    if not root.exists():raise Error(f"benchmark path does not exist: {root}")
    p=sorted(root.rglob("manifest.json"),key=lambda x:x.as_posix().lower())
    if not p:raise Error(f"no manifest.json under {root}")
    return p

def load_run(p):
    m=load_manifest(p); tasks=load_csv(p.parent/m["ticktask_csv"])
    return {"run_id":m["run_id"],"variant":m["variant"],"threads":m["task_thread_count"],
            "wall":float(m["wall_clock_seconds"]),"repeat":m.get("repeat"),"warmup":bool(m.get("warmup",False)),
            "manifest":m,"tasks":tasks}

def cv(v):
    if len(v)<2:return None
    m=statistics.mean(v)
    return statistics.stdev(v)/m if m else None

def noise(c, threshold):
    return None if c is None else c > threshold

def noise_label(value):
    return "unknown" if value is None else ("yes" if value else "no")

def combined_noise(*values):
    if any(x is True for x in values):return True
    if any(x is None for x in values):return None
    return False

def group(runs,threshold):
    walls=[r["wall"] for r in runs]; names=sorted({n for r in runs for n in r["tasks"]})
    tasks=[]
    for n in names:
        rows=[r["tasks"][n] for r in runs if n in r["tasks"]]
        totals=[x["total_ms"] for x in rows]; c=cv(totals)
        tasks.append({"task":n,"mean_total_ms":statistics.mean(totals),"median_total_ms":statistics.median(totals),
                      "max_total_ms":max(totals),"mean_calls":statistics.mean(x["calls"] for x in rows),
                      "max_record_ms":max(x["max_record_ms"] for x in rows),
                      "longest_lock_ms":max(x["longest_lock_ms"] for x in rows),
                      "total_ms_cv":c,"noisy":noise(c,threshold),"runs_present":len(rows),
                      "repeatability_assessed":len(rows)>=3 and c is not None})
    wc=cv(walls)
    return {"runs":len(runs),"wall_clock_seconds":{"mean":statistics.mean(walls),"median":statistics.median(walls),
            "min":min(walls),"max":max(walls),"stdev":statistics.stdev(walls) if len(walls)>1 else None,
            "cv":wc,"noisy":noise(wc,threshold),"repeatability_assessed":len(walls)>=3 and wc is not None},
            "tasks_by_cost":sorted(tasks,key=lambda x:(-x["mean_total_ms"],x["task"])),
            "tasks_by_lock":sorted(tasks,key=lambda x:(-x["longest_lock_ms"],x["task"]))}

def report(runs,threshold=.03):
    runs=[r for r in runs if not r["warmup"]]
    if not runs:raise Error("no measured runs")
    keyed={}
    for r in runs:keyed.setdefault((r["variant"],r["threads"]),[]).append(r)
    groups=[]
    for (variant,threads),rs in sorted(keyed.items()):
        g=group(rs,threshold);g.update({"variant":variant,"task_thread_count":threads});groups.append(g)
    scaling=[]
    for variant in sorted({g["variant"] for g in groups}):
        gs=[g for g in groups if g["variant"]==variant];one=next((g for g in gs if g["task_thread_count"]==1),None)
        base=one["wall_clock_seconds"]["median"] if one else None;best=min(g["wall_clock_seconds"]["median"] for g in gs)
        for g in gs:
            w=g["wall_clock_seconds"]["median"];scaling.append({"variant":variant,"task_thread_count":g["task_thread_count"],
                "median_wall_clock_seconds":w,"speedup_vs_1_thread":base/w if base else None,
                "relative_to_best":w/best,"noisy":g["wall_clock_seconds"]["noisy"],
                "repeatability_assessed":g["wall_clock_seconds"]["repeatability_assessed"]})
    variants=sorted({g["variant"] for g in groups}); comparisons=[]
    if len(variants)>1:
        b="vanilla" if "vanilla" in variants else variants[0]
        for t in sorted({g["task_thread_count"] for g in groups}):
            bg=next((g for g in groups if g["variant"]==b and g["task_thread_count"]==t),None)
            if not bg:continue
            bw=bg["wall_clock_seconds"]["median"]
            for g in groups:
                if g["task_thread_count"]!=t or g["variant"]==b:continue
                w=g["wall_clock_seconds"]["median"];comparisons.append({"baseline_variant":b,"variant":g["variant"],
                    "task_thread_count":t,"baseline_median_wall_clock_seconds":bw,"variant_median_wall_clock_seconds":w,
                    "wall_clock_change_fraction":(w-bw)/bw,"speedup":bw/w,
                    "noisy":combined_noise(bg["wall_clock_seconds"]["noisy"],g["wall_clock_seconds"]["noisy"]),
                    "repeatability_assessed":bg["wall_clock_seconds"]["repeatability_assessed"] and g["wall_clock_seconds"]["repeatability_assessed"]})
    return {"format_version":2,"run_count":len(runs),"noisy_cv_threshold":threshold,"variants":variants,
            "groups":groups,"scaling":scaling,"comparisons":comparisons,
            "warning":"Timing/lock metrics identify hotspots and correlation only; do not infer causality from one metric. Unknown variance is not zero noise; at least three matched runs per condition are required to assess repeatability. A low CV is not a significance test."}

def f(x,d=3):return "n/a" if x is None else f"{x:.{d}f}"

def markdown(d,top):
    L=["# Victoria 3 benchmark analysis","",f"Measured runs: **{d['run_count']}**","","> "+d["warning"],"",
       "## Scaling","","| Variant | Threads | Runs | Median wall-clock (s) | Speedup vs 1 thread | CV | Noise | Repeatability assessed |",
       "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    lookup={(g["variant"],g["task_thread_count"]):g for g in d["groups"]}
    for s in d["scaling"]:
        c=lookup[(s["variant"],s["task_thread_count"])]["wall_clock_seconds"]["cv"]
        g=lookup[(s["variant"],s["task_thread_count"])]
        L.append(f"| {s['variant']} | {s['task_thread_count']} | {g['runs']} | {f(s['median_wall_clock_seconds'])} | {f(s['speedup_vs_1_thread'])}× | {f(c*100 if c is not None else None,2)}% | {noise_label(s['noisy'])} | {'yes' if g['wall_clock_seconds']['repeatability_assessed'] else 'no'} |")
    for g in d["groups"]:
        L+=["",f"## {g['variant']} — {g['task_thread_count']} task threads","",
            f"Runs: {g['runs']}; wall-clock median: {g['wall_clock_seconds']['median']:.3f}s; CV: {f(g['wall_clock_seconds']['cv']*100 if g['wall_clock_seconds']['cv'] is not None else None,2)}%; noise: {noise_label(g['wall_clock_seconds']['noisy'])}; repeatability assessed: {'yes' if g['wall_clock_seconds']['repeatability_assessed'] else 'no'}","",
            f"### Top {top} TickTasks by cumulative cost","",
            "| Task | Mean total ms | Mean calls | Max record ms | Longest lock ms | CV | Noise |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
        for x in g["tasks_by_cost"][:top]:
            L.append(f"| {x['task']} | {x['mean_total_ms']:.3f} | {x['mean_calls']:.1f} | {x['max_record_ms']:.3f} | {x['longest_lock_ms']:.3f} | {f(x['total_ms_cv']*100 if x['total_ms_cv'] is not None else None,2)}% | {noise_label(x['noisy'])} |")
        L+=["",f"### Top {top} TickTasks by longest lock","","| Task | Longest lock ms | Mean total ms | Mean calls |","| --- | ---: | ---: | ---: |"]
        for x in g["tasks_by_lock"][:top]:L.append(f"| {x['task']} | {x['longest_lock_ms']:.3f} | {x['mean_total_ms']:.3f} | {x['mean_calls']:.1f} |")
    L+=["","## Interpretation guardrails","","- Treat `longest_lock` as a lead for OS-level wait profiling, not proof of root cause.","- A high-cost task may still scale well internally.","- Do not optimize differences smaller than benchmark noise.","- Simulation wall-clock throughput is the primary outcome; CPU utilization is diagnostic.",""]
    return "\n".join(L)

# Stable names used by tests and future callers.
BenchmarkError = Error
load_ticktask_csv = load_csv
discover_manifests = discover
build_report = report

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("path",type=Path);p.add_argument("--json",dest="jp",type=Path);p.add_argument("--markdown",dest="mp",type=Path);p.add_argument("--top",type=int,default=20);p.add_argument("--noisy-cv-threshold",type=float,default=.03)
    a=p.parse_args(argv)
    try:d=report([load_run(x) for x in discover(a.path)],a.noisy_cv_threshold)
    except (Error,OSError) as e:print(f"error: {e}",file=sys.stderr);return 2
    if a.jp:a.jp.parent.mkdir(parents=True,exist_ok=True);a.jp.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if a.mp:a.mp.parent.mkdir(parents=True,exist_ok=True);a.mp.write_text(markdown(d,a.top),encoding="utf-8")
    if not a.jp and not a.mp:sys.stdout.write(markdown(d,a.top))
    return 0

if __name__=="__main__":raise SystemExit(main())
