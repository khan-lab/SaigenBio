"""Deterministic artifact comparisons; no claim of biological equivalence."""
import csv
import math

from .records import RecordError
from .store import digest


def compare(original, candidate, criterion):
    if criterion['method']=='sha256':
        left,right=digest(original),digest(candidate)
        return {'status':'match' if left==right else 'different','originalSha256':left,'candidateSha256':right,
                'meaning':'Exact byte equality only.'}
    keys,columns=criterion['keyColumns'],criterion['columns']
    delimiter=criterion.get('delimiter',',')
    def table(path):
        with path.open(encoding='utf-8-sig',newline='') as handle:
            reader=csv.DictReader(handle,delimiter=delimiter)
            header=reader.fieldnames
            if not header or len(set(header))!=len(header) or not set(keys+columns)<=set(header):
                raise RecordError('Missing or duplicate comparison columns')
            result={}
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise RecordError('Malformed table row')
                key=tuple(row[k] for k in keys)
                if any(not v for v in key) or key in result:
                    raise RecordError('Missing or duplicate table key')
                try:
                    values=[float(row[c]) for c in columns]
                except (TypeError,ValueError) as exc:
                    raise RecordError('Non-numeric comparison value') from exc
                if not all(math.isfinite(v) for v in values):
                    raise RecordError('Non-finite comparison value')
                result[key]=values
                if len(result)>100000:
                    raise RecordError('Numeric comparison is limited to 100,000 rows per artifact')
            return result,sorted(set(header)-set(keys+columns))
    left,ignored_left=table(original);right,ignored_right=table(candidate)
    common=left.keys()&right.keys()
    differences=[];count=0;max_difference=0.0
    for key in sorted(common):
        for column,a,b in zip(columns,left[key],right[key]):
            difference=abs(a-b)
            max_difference=max(max_difference,difference)
            if not math.isclose(a,b,rel_tol=criterion['rtol'],abs_tol=criterion['atol']):
                count+=1
                if len(differences)<20:
                    differences.append({'key':list(key),'column':column,'original':a,'candidate':b})
    missing=sorted(left.keys()-right.keys());added=sorted(right.keys()-left.keys())
    return {'status':'match' if not count and not missing and not added else 'different',
            'originalRows':len(left),'candidateRows':len(right),'comparedRows':len(common),
            'differentValues':count,'maximumAbsoluteDifference':max_difference if math.isfinite(max_difference) else 'overflow',
            'missingKeyCount':len(missing),'addedKeyCount':len(added),
            'missingKeys':[list(k) for k in missing[:20]],'addedKeys':[list(k) for k in added[:20]],
            'differenceExamples':differences,'exampleLimit':20,'atol':criterion['atol'],'rtol':criterion['rtol'],
            'keyColumns':keys,'columns':columns,'uncomparedOriginalColumns':ignored_left,
            'uncomparedCandidateColumns':ignored_right,
            'meaning':'Rows matched by the specified exact keys. Only the listed numeric columns and row membership were tested. Numeric match uses abs(a-b) <= max(atol, rtol * max(abs(a), abs(b))).'}
