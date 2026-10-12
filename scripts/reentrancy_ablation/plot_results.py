"""Render completed paired experiments; no training or source-data writes."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from common import *

def main():
    root=HERE/"artifacts/v1";data=read_json(root/"summary.json")
    index={(x["task"],x["experiment"]):x for x in data["experiments"] if x["seed"]==1}
    fig,axes=plt.subplots(1,3,figsize=(18,6),gridspec_kw={"width_ratios":[1.05,1.05,1.2]})
    labels={"A_author":"Author graph reference","B_local_labels":"Local labels only",
            "C_local_relations":"Local relations only","D_local_features":"Local tokens only",
            "T_validation_legacy":"Legacy validation","T_lr_legacy":"Legacy scheduler",
            "T_gradient_detached":"Detached HGT gradient","T_delta_legacy":"Legacy delta",
            "T_upstream_behavior":"Combined legacy (last)"}
    order=list(labels)
    for ax,task,paper,title in [(axes[0],"node",96.78,"Node task: 10-fold mean"),
                               (axes[1],"contract",91.67,"Contract task: 5-fold mean")]:
        xs=[index[(task,k)] for k in order if (task,k) in index]
        values=[x["primary_metrics"]["buggy_f1"] for x in xs];ys=np.arange(len(xs))
        ax.scatter(values,ys,s=45,color=["#cb4b16" if x["experiment"]=="B_local_labels" else "#2878a0" for x in xs],zorder=3)
        for y,x in zip(ys,values):ax.annotate(f"{x:.2f}",(x,y),xytext=(5,7),textcoords="offset points",fontsize=9)
        ax.axvline(paper,color="gray",ls="--",lw=1,label=f"Paper: {paper:.2f}")
        ax.set_yticks(ys);ax.set_yticklabels([labels[x["experiment"]] for x in xs],fontsize=9)
        ax.margins(y=.13);ax.invert_yaxis();ax.set_xlabel("Buggy-F1 (%)");ax.set_title(title)
        ax.set_xlim(min(values+[paper])-2,min(101,max(values+[paper])+2));ax.grid(axis="x",alpha=.25)
        ax.legend(loc="center left",fontsize=8)
    ax=axes[2]
    if ("node","B_local_labels") in index:
        a=index[("node","A_author")];b=index[("node","B_local_labels")]
        folds=[x["fold"] for x in a["fold_values"]]
        av=[x["best"]["buggy_f1"] for x in a["fold_values"]]
        bv=[x["best"]["buggy_f1"] for x in b["fold_values"]]
        ba=[x["author_best"]["buggy_f1"] for x in b["fold_values"]]
        ax.plot(folds,av,"o-",label="A: author labels",color="#2878a0")
        ax.plot(folds,bv,"s-",label="B: own local labels",color="#cb4b16")
        ax.plot(folds,ba,"^--",label="B: scored on author labels",color="#558b2f")
        ax.set_xticks(folds);ax.set_xlabel("Fixed validation fold");ax.set_ylabel("Buggy-F1 (%)")
        ax.set_title("Labels: paired fold comparison");ax.grid(alpha=.25);ax.legend(fontsize=8,loc="lower right")
    fig.suptitle("Reentrancy ablations: fixed splits and initialization, seed 1",fontsize=14)
    fig.text(.5,.02,"B changes the target labels. Other rows keep author labels. Best-loss weights except combined legacy. Paper is a reference, not identical folds.",ha="center",fontsize=9)
    fig.tight_layout(rect=[0,.05,1,.94])
    for ext in ["png","pdf"]:fig.savefig(str(root/("comparison."+ext)),dpi=180,bbox_inches="tight")
    plt.close(fig)
    print(root/"comparison.png")
if __name__=="__main__":main()
