"""Record real filtering, statistics and figures without changing ecoli-evol."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from saigen.store import Store, entity, digest
from saigen.runner import run, code_info

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--project",type=Path,default=Path(".saigen-projects/ecoli"))
    args=parser.parse_args()
    source=args.source.expanduser().resolve()
    names=["SRR2589044","SRR2584863","SRR2584866"]
    vcfs=[source/"results"/"bcf"/(n+"_variants.vcf") for n in names]
    metadata=source/"metadata"/"samples.tsv"
    tools=source/".pixi"/"envs"/"pipeline"/"bin"
    for p in [*vcfs,metadata,tools/"bcftools",tools/"vcfutils.pl"]:
        if not p.is_file():raise SystemExit(f"Required source file is missing: {p}")
    store=Store(args.project);store.init("ecoli-evol · recorded")
    root=store.snapshot("Unfiltered variants",[*vcfs,metadata],note="Existing VCFs and sample metadata imported from ecoli-evol. Historical upstream execution is not reconstructed.",code=code_info(source))
    helper=Path(__file__).resolve().with_name("ecoli_steps.py")
    initial={a["name"]:a["id"] for a in store.flow()["artifacts"].values() if a["id"] in root["artifactIds"]}
    meta="artifact:"+initial["samples.tsv"]
    inputs=["artifact:"+initial[p.name] for p in vcfs]
    branches={}
    summary={}
    def record(parents,title,argv,**kwargs):
        result=run(store,parents,title,argv,source_repo=source,scripts=[str(helper)],environment_files=[str(source/"pixi.lock")],**kwargs)
        print(json.dumps(result),flush=True)
        if result["status"]!="completed":raise RuntimeError(result["error"] or "Example action failed")
        return entity(store.flow(),"states",result["state"])
    def artifact_inputs(n,extension=None):
        return ["artifact:"+a["id"] for a in (store.flow()["artifacts"][i] for i in n["artifactIds"]) if extension is None or a["name"].endswith(extension)]
    for depth in (2,10):
        command=[sys.executable,str(helper),"filter","--tool",str(tools/"vcfutils.pl"),"--depth",str(depth),"--inputs",*[f"{{input:{i}}}" for i in range(3)],"--names",*names]
        branch=record([root["id"]],f"Depth {depth}",command,inputs=inputs,outputs=[n+".vcf" for n in names],label=f"varFilter · -d {depth}",reason=f"Compare the retained calls with minimum read depth {depth}.")
        branches[depth]=branch
        command=[sys.executable,str(helper),"stats","--tool",str(tools/"bcftools"),"--inputs",*[f"{{input:{i}}}" for i in range(3)],"--names",*names,"--metadata","{input:3}"]
        stats=record([branch["id"]],"Counts by generation",command,inputs=artifact_inputs(branch)+[meta],outputs=["counts.tsv"]+[n+".stats.txt" for n in names],label="bcftools stats + metadata",reason="Connect observed VCF record counts to sample generation and mutator metadata.")
        summary[depth]=stats
        counts=artifact_inputs(stats,".tsv")
        linear=record([stats["id"]],"Counts · linear scale",[sys.executable,str(helper),"plot","--input","{input:0}","--scale","linear"],inputs=counts,outputs=["counts.svg"],label="plot · --scale linear",reason="Inspect absolute differences between the three samples.")
        record([linear["id"]],"Counts · log scale",[sys.executable,str(helper),"plot","--input","{input:0}","--scale","log"],inputs=counts,outputs=["counts.svg"],label="plot · --scale log",reason="Keep the linear view and add a log view to examine the smaller counts.")
    # Deliberately use a wrong filename to demonstrate a real failed process and retry.
    failed=run(store,[summary[10]["id"]],"Plot attempt · missing input",[sys.executable,str(helper),"plot","--input","missing-counts.tsv"],outputs=["counts.svg"],source_repo=source,scripts=[str(helper)],label="plot · wrong input path",reason="Recorder acceptance example: deliberately exercise a missing-file failure, preserving the attempt.")
    print(json.dumps(failed),flush=True)
    record([summary[10]["id"]],"Plot retry · corrected input",[sys.executable,str(helper),"plot","--input","{input:0}"],inputs=artifact_inputs(summary[10],".tsv"),outputs=["counts.svg"],label="plot · corrected path",reason=f"Retry of {failed['action']}: use the preserved count table instead of the missing path.")
    comparison=record([branches[2]["id"],branches[10]["id"]],"Shared and changed calls",[sys.executable,str(helper),"compare","--left",*[f"{{input:{i}}}" for i in range(3)],"--right",*[f"{{input:{i}}}" for i in range(3,6)],"--names",*names],inputs=artifact_inputs(branches[2])+artifact_inputs(branches[10]),outputs=["comparison.json","changed-sites.tsv","review-notes.md"],label="compare · depth 2 / 10",reason="Identify shared calls and branch-specific sites for subsequent read-level review.")
    print(json.dumps({"project":str(store.root),"comparisonState":comparison["id"],"next":f"python3 -m saigen --project {args.project} serve"}),flush=True)
if __name__=="__main__":main()
