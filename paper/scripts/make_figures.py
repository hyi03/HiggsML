"""Reproduce paper graphics and tables from the checked aggregate snapshot."""
from pathlib import Path
import json
from statistics import median
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import argparse
from paper_snapshot import load_snapshot

PAPER_DIR = Path(__file__).resolve().parents[1]
LATEX_DIR = PAPER_DIR / "latex"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot-dir', type=Path)
parser.add_argument('--refreshed', action='store_true', help='Accept a newly verified provenance for identical pinned result bytes.')
args = parser.parse_args()
DATA = load_snapshot(args.snapshot_dir, refreshed=args.refreshed)
FIG = LATEX_DIR / "figures"
GEN = LATEX_DIR / "generated"
FIG.mkdir(exist_ok=True)
GEN.mkdir(exist_ok=True)
SEEDS = DATA["seeds"]
W = {(r["seed"], r["subset"]): r["width68"] for r in DATA["records"]}
AUC = {(r["seed"], r["subset"]): r["auc"] for r in DATA["records"]}
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]
ORDER = sorted(DATA["subsets"][1:], key=lambda g: (median(W[s,g] for s in SEEDS), len(g), g))
plt.rcParams.update({"font.family":"serif", "font.serif":["DejaVu Serif"], "font.size":9,
                     "axes.labelsize":10, "legend.fontsize":8, "xtick.labelsize":8,
                     "ytick.labelsize":8, "axes.spines.top":False, "axes.spines.right":False,
                     "pdf.fonttype":42, "ps.fonttype":42, "savefig.bbox":"tight"})


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", metadata={"Creator":"HiggsML paper aggregate plotting", "CreationDate":None})
    fig.savefig(FIG / f"{name}.png", dpi=180)
    plt.close(fig)


fig, ax = plt.subplots(figsize=(6.9, 4.0), layout="constrained")
ys = np.arange(len(ORDER))
for i, seed in enumerate(SEEDS):
    ax.scatter([W[seed,g] for g in ORDER], ys+(i-2)*.095, s=22, color=COLORS[i], label=str(seed), zorder=3)
ax.scatter([median(W[s,g] for s in SEEDS) for g in ORDER], ys, marker="|", s=160, color="black", label="Median", zorder=4)
ax.axvline(W[42,""], color="0.4", linestyle="--", linewidth=1, label="Constant baseline")
ax.set(yticks=ys, yticklabels=ORDER, xlabel=r"Expected interval width $W_{68}$", ylabel="Feature subset")
ax.invert_yaxis()
ax.grid(axis="x", alpha=.18)
ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(.5,1.01), frameon=False, title="Training seed; points share the same MC")
save(fig, "subset_widths")

fig, ax = plt.subplots(figsize=(3.35, 2.65), layout="constrained")
for subset, color, marker in [("BC",COLORS[0],"o"),("AC",COLORS[1],"s")]:
    vals = [100*(1-W[s,subset]/W[s,"ABCD"]) for s in SEEDS]
    ax.plot(SEEDS, vals, marker=marker, color=color, markersize=4, linewidth=1, label=subset)
ax.axhline(0,color="0.4",linewidth=.8,linestyle="--")
ax.set(xlabel="Training seed", ylabel=r"Reduction of $W_{68}$ vs ABCD (%)", xticks=SEEDS)
ax.grid(axis="y",alpha=.18)
ax.legend(frameon=False, ncol=2, loc="upper left")
save(fig,"compact_comparisons")

fig, ax = plt.subplots(figsize=(3.35,2.7), layout="constrained")
for j, row in enumerate(DATA["attribution"]):
    for i, val in enumerate(row["per_seed"]):
        ax.scatter(val,j+(i-2)*.075,s=22,color=COLORS[i],zorder=3)
    ax.scatter(row["median"],j,marker="|",s=170,color="black",zorder=4)
ax.axvline(0,color="0.4",linewidth=.8,linestyle="--")
ax.set(yticks=range(4),yticklabels=list("ABCD"),xlabel=r"Shapley contribution $phi_G$ ($W_{68}$ units)",ylabel="Feature group")
ax.invert_yaxis()
ax.grid(axis="x",alpha=.18)
save(fig,"shapley")

fig, ax = plt.subplots(figsize=(3.35,3.0), layout="constrained")
for i,seed in enumerate(SEEDS):
    ax.scatter([AUC[seed,g] for g in ORDER],[W[seed,g] for g in ORDER],s=9,color=COLORS[i],alpha=.35,edgecolors="none")
offsets={"BC":(-19,-13),"AC":(4,-11),"ABCD":(4,3),"A":(-13,4),"B":(-10,5),"C":(-10,4),"D":(4,-3),"AB":(3,6),"BCD":(-25,4)}
for subset in ORDER:
    x,y=median(AUC[s,subset] for s in SEEDS),median(W[s,subset] for s in SEEDS)
    ax.scatter(x,y,s=18,color="black",zorder=4)
    if subset in offsets:
        ax.annotate(subset,(x,y),xytext=offsets[subset],textcoords="offset points",fontsize=8)
ax.set(xlabel="Validation absolute-weight AUC",ylabel=r"Expected interval width $W_{68}$")
ax.grid(alpha=.15)
save(fig,"auc_width")

# Single numeric source for prose, captions, and tables. No likelihood refits.
commands = {}
for subset in ["", "BC", "AC", "ABCD"]:
    name = subset or "Empty"
    commands[f"Width{name}"] = f"{median(W[s,subset] for s in SEEDS):.5f}"
    if subset:
        commands[f"Gain{name}"] = f"{median(100*(1-W[s,subset]/W[s,'']) for s in SEEDS):.2f}"
for subset in ["BC","AC"]:
    commands[f"PairGain{subset}"] = f"{median(100*(1-W[s,subset]/W[s,'ABCD']) for s in SEEDS):.2f}"
for row in DATA["attribution"]:
    commands[f"Phi{row['group']}"] = f"{row['median']:.5f}"
for stage, prefix in [("assessment","Assessment"),("t2","Ttwo")]:
    for subset in ["BC","AC","ABCD"]:
        for level, suffix in [("0.68","SixtyEight"),("0.95","NinetyFive")]:
            row = next(r for r in DATA["diagnostics"] if r["stage"] == stage and float(r["mu"]) == 1 and r["subset"] == subset and r["confidence_level"] == level and r["metric"] == "conditional_coverage")
            commands[prefix+subset+suffix] = (
                f"{float(row['median']):.4f}"
                if row["status"] == "valid" and row["median"]
                else r"\textemdash{}"
            )
(GEN/"numbers.tex").write_text("% Generated from checked aggregate results.\n"+"\n".join(
    f"\\newcommand{{\\{key}}}{{{val}}}" for key,val in commands.items())+"\n",encoding="utf-8")
nominal=[]
for subset in [""]+ORDER:
    vals=[W[s,subset] for s in SEEDS]
    auc="---" if not subset else f"{median(AUC[s,subset] for s in SEEDS):.5f}"
    label=subset or r"$\varnothing$"
    nominal.append(label+" & "+" & ".join(f"{v:.5f}" for v in vals)+f" & {median(vals):.5f} & {auc} \\\\")
(GEN/"nominal_rows.tex").write_text("\n".join(nominal)+"\n",encoding="utf-8")
interaction_rows=[]
for r in DATA["interactions"]:
    pair=r["pair"]
    if pair.startswith("["):pair="".join(json.loads(pair))
    cond=r["conditioning_subset"] or r"$\varnothing$"
    interaction_rows.append(pair+" & "+cond+" & "+" & ".join(f"{v:+.5f}" for v in r["per_seed"])+f" & {r['median']:+.5f} \\\\")
(GEN/"interaction_rows.tex").write_text("\n".join(interaction_rows)+"\n",encoding="utf-8")
print(json.dumps({"figures":4,"generated_tables":2,"numbers":commands},indent=2))
