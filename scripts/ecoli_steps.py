"""Small, explicit helpers for the recorded ecoli-evol example."""
import argparse
import csv
import html
import json
import math
from pathlib import Path
import shlex
import subprocess

def execute(argv, output):
    print(shlex.join(argv),flush=True)
    with Path(output).open("wb") as stream:
        subprocess.run(argv,stdout=stream,check=True)

def records(path):
    out=[]
    with Path(path).open() as f:
        for line in f:
            if not line.startswith("#"):
                parts=line.rstrip().split("\t")
                if len(parts)>=8: out.append(parts)
    return out

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    q=sub.add_parser("filter");q.add_argument("--tool",required=True);q.add_argument("--depth",type=int,required=True);q.add_argument("--inputs",nargs="+",required=True);q.add_argument("--names",nargs="+",required=True)
    q=sub.add_parser("stats");q.add_argument("--tool",required=True);q.add_argument("--inputs",nargs="+",required=True);q.add_argument("--names",nargs="+",required=True);q.add_argument("--metadata",required=True)
    q=sub.add_parser("plot");q.add_argument("--input",required=True);q.add_argument("--scale",choices=["linear","log"],default="linear");q.add_argument("--output",default="counts.svg")
    q=sub.add_parser("compare");q.add_argument("--left",nargs="+",required=True);q.add_argument("--right",nargs="+",required=True);q.add_argument("--names",nargs="+",required=True)
    a=p.parse_args()
    if a.mode=="filter":
        if len(a.inputs)!=len(a.names):p.error("Input and sample counts differ")
        for source,name in zip(a.inputs,a.names):
            execute([a.tool,"varFilter","-d",str(a.depth),source],name+".vcf")
    elif a.mode=="stats":
        if len(a.inputs)!=len(a.names):p.error("Input and sample counts differ")
        with Path(a.metadata).open() as f:
            metadata={r["sample"]:r for r in csv.DictReader(f,delimiter="\t")}
        with Path("counts.tsv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=["sample","generation","mutator","variants","snps","indels"],delimiter="\t");writer.writeheader()
            for source,name in zip(a.inputs,a.names):
                execute([a.tool,"stats",source],name+".stats.txt")
                rows=records(source)
                # Count VCF records, classifying records that contain an indel separately.
                indels=sum(any(len(alt)!=len(row[3]) for alt in row[4].split(",")) for row in rows)
                writer.writerow({"sample":name,"generation":metadata[name]["generation"],"mutator":metadata[name]["mutator"],"variants":len(rows),"snps":len(rows)-indels,"indels":indels})
    elif a.mode=="plot":
        with Path(a.input).open() as f: rows=list(csv.DictReader(f,delimiter="\t"))
        if not rows: raise ValueError("The count table is empty")
        counts=[int(r["variants"]) for r in rows]
        if a.scale=="log" and any(v<=0 for v in counts): raise ValueError("A log plot requires positive counts")
        scaled=[math.log10(v) if a.scale=="log" else v for v in counts]
        maxv=max(scaled) or 1
        parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 340"><rect width="760" height="340" fill="white"/>',
               '<text x="56" y="32" font-family="sans-serif" font-size="18" fill="#263d35">Retained variant records</text>',
               '<path d="M60 60V270H720" fill="none" stroke="#b8c7af"/>']
        for i in range(5):
            y=270-i*50
            value=maxv*i/4
            label=f"{10**value:.0f}" if a.scale=="log" else f"{value:.0f}"
            parts.append(f'<path d="M60 {y}H720" stroke="#e8ede3"/><text x="50" y="{y+4}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#75856a">{label}</text>')
        for i,(row,value) in enumerate(zip(rows,scaled)):
            x=120+i*(550/max(1,len(rows)-1))
            h=value/maxv*200
            parts.append(f'<rect x="{x-30}" y="{270-h}" width="60" height="{h}" rx="3" fill="#829e6f"/><text x="{x}" y="{259-h}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#425f35">{counts[i]}</text><text x="{x}" y="294" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#748168">{html.escape(row["generation"])}</text>')
        parts.append(f'<text x="380" y="325" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#748168">Generation · {a.scale} scale · observed VCF record counts</text></svg>')
        Path(a.output).write_text("".join(parts))
    elif a.mode=="compare":
        if len(a.left)!=len(a.right) or len(a.left)!=len(a.names):p.error("Sample counts differ")
        summaries=[]
        with Path("changed-sites.tsv").open("w",newline="") as f:
            writer=csv.writer(f,delimiter="\t");writer.writerow(["sample","chrom","position","ref","alt","branch"])
            for left,right,name in zip(a.left,a.right,a.names):
                keys=lambda path:{(r[0],r[1],r[3],r[4]) for r in records(path)}
                l,r=keys(left),keys(right)
                summaries.append({"sample":name,"shared":len(l&r),"depth2_only":len(l-r),"depth10_only":len(r-l)})
                for key in sorted(l-r):writer.writerow([name,*key,"depth2"])
                for key in sorted(r-l):writer.writerow([name,*key,"depth10"])
        Path("comparison.json").write_text(json.dumps(summaries,indent=2)+"\n")
        Path("review-notes.md").write_text("# Depth threshold comparison\n\nThese counts describe which variant records survive the two filtering commands. They do not establish that a retained variant is causal or that a removed variant is false.\n\nThe changed-sites table identifies candidates for review against the saved read alignments. This example does not perform that read-level validation.\n\n"+json.dumps(summaries,indent=2)+"\n")
if __name__=="__main__":main()
