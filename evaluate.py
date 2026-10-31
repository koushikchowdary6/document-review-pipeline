"""Exact-span synthetic PII evaluation. No model training or provider calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from integrity import loads, read_text
from redactor import detect


def load_cases(path):
    data=loads(read_text(path))
    if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data.get('schema_version') != 1 or not isinstance(data.get('cases'),list) or not data['cases']:
        raise ValueError('Dataset must contain nonempty cases')
    ids=set()
    for case in data['cases']:
        if not isinstance(case,dict) or not isinstance(case.get('id'),str) or not re.fullmatch('[a-z0-9_-]{1,64}',case['id']) or case['id'] in ids:
            raise ValueError('Invalid or duplicate case ID')
        ids.add(case['id'])
        if (set(case) != {'id','text','entities'} or not isinstance(case.get('text'),str)
                or len(case['text']) > 10000 or not isinstance(case.get('entities'),list)):
            raise ValueError('Invalid case text or labels')
        previous=0
        labels=set()
        for entity in case['entities']:
            if (not isinstance(entity,dict) or set(entity) != {'kind','start','end'}
                    or not isinstance(entity['kind'],str) or not re.fullmatch('[A-Z][A-Z0-9_]*',entity['kind'])
                    or type(entity['start']) is not int or type(entity['end']) is not int
                    or not 0 <= entity['start'] < entity['end'] <= len(case['text'])):
                raise ValueError('Invalid annotation span')
            label=(entity['kind'],entity['start'],entity['end'])
            if label in labels:
                raise ValueError('Duplicate ground-truth entity span')
            labels.add(label)
            if entity['start'] < previous:
                raise ValueError('Overlapping or out-of-order annotation spans')
            previous=entity['end']
    return data


def rates(tp,fp,fn):
    return {'true_positives':tp,'false_positives':fp,'false_negatives':fn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}


def evaluate(path):
    data=load_cases(path)
    counts=Counter();kinds={};rows=[];negative_docs=0;flagged_negative_docs=0
    for case in data['cases']:
        expected={(e['kind'],e['start'],e['end']) for e in case['entities']}
        # Do not silently collapse duplicate predictions into a set or count
        # impossible spans as valid false positives. A broken detector adapter
        # must fail evaluation rather than publishing misleading precision.
        actual=set()
        previous_end=0
        for finding in detect(case['text']):
            kind,start,end=finding.kind,finding.start,finding.end
            if (not isinstance(kind,str) or not re.fullmatch('[A-Z][A-Z0-9_]*',kind)
                    or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(case['text'])):
                raise ValueError('Invalid detector prediction span')
            if start < previous_end:
                raise ValueError('Overlapping or out-of-order detector predictions')
            prediction=(kind,start,end)
            if prediction in actual:
                raise ValueError('Duplicate detector prediction span')
            actual.add(prediction)
            previous_end=end
        tp,fp,fn=actual & expected,actual-expected,expected-actual
        counts.update(tp=len(tp),fp=len(fp),fn=len(fn))
        for kind in {x[0] for x in expected | actual}:
            c=kinds.setdefault(kind,Counter())
            c.update(tp=sum(x[0]==kind for x in tp),fp=sum(x[0]==kind for x in fp),fn=sum(x[0]==kind for x in fn))
        if not expected:
            negative_docs+=1;flagged_negative_docs+=bool(actual)
        def public(spans):return [dict(zip(['kind','start','end'],e)) for e in sorted(spans)]
        rows.append({'id':case['id'],'false_positives':public(fp),'false_negatives':public(fn),'true_positive_count':len(tp)})
    return {'schema_version':1,'dataset_sha256':hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'detector_sha256':hashlib.sha256(Path(__file__).with_name('redactor.py').read_bytes()).hexdigest(),
            'matching':'Exact kind + original-text character span; micro-averaged entities',
            'case_count':len(data['cases']),'overall':rates(counts['tp'],counts['fp'],counts['fn']),
            'negative_documents':negative_docs,'flagged_negative_documents':flagged_negative_docs,
            'negative_document_false_positive_rate':flagged_negative_docs/negative_docs if negative_docs else None,
            'by_kind':{k:rates(c['tp'],c['fp'],c['fn']) for k,c in sorted(kinds.items())},'cases':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,default=Path(__file__).parent/'fixtures/pii_eval.json')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    try:
        result=evaluate(args.dataset)
        serialized=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n'
        if args.output:
            with args.output.open('x',encoding='utf-8') as stream:stream.write(serialized)
        print(serialized,end='')
    except (ValueError,OSError,UnicodeError,RecursionError):
        p.exit(1,'Evaluation rejected: check dataset labels and output destination.\n')
