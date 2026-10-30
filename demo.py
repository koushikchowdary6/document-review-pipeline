"""Synthetic-only review walkthrough; interactive unless --scripted is explicit."""
import argparse
import json
from pathlib import Path
from decision import decide, export_approved, inspect_bundle, review_status
from review import build
from evaluate import evaluate


def blocked(bundle,destination):
    try:
        export_approved(bundle,destination)
    except (OSError,ValueError):
        assert not destination.exists()
        return True
    raise AssertionError('Expected export to be blocked')


def run(output,scripted=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=Path(__file__).parent/'examples/synthetic.txt'
    print('SYNTHETIC INPUT (no real customer data):\n'+source.read_text())
    bundle=output/'bundle';build(source,bundle)
    print('REVIEW VIEW:\n'+json.dumps(inspect_bundle(bundle,True),indent=2))
    assert blocked(bundle,output/'unapproved.txt')
    print('PASS: pending export blocked')
    if not scripted:
        choice=input('Inspect the sanitized synthetic text above. Type approve or reject: ').strip().lower()
        if choice!='approve':
            decide(bundle,'rejected','local demo reviewer','Synthetic walkthrough rejected by operator')
            assert blocked(bundle,output/'rejected.txt')
            print('Rejected; export blocked. Choose a new output directory to repeat.')
            return {'status':'rejected'}
    decide(bundle,'approved','scripted synthetic reviewer' if scripted else 'local demo reviewer',
           'Scripted synthetic control demonstration, not a real human review' if scripted else 'Operator inspected synthetic walkthrough text')
    export_approved(bundle,output/'approved.txt')
    print('PASS: approved sanitized text exported')
    (bundle/'sanitized.txt').write_text('tampered synthetic content')
    assert blocked(bundle,output/'tampered.txt')
    print('PASS: export after tampering blocked')
    rejected=output/'rejected-bundle';build(source,rejected)
    decide(rejected,'rejected','synthetic reviewer','Synthetic rejected-state control')
    assert blocked(rejected,output/'rejected.txt')
    report=evaluate(Path(__file__).parent/'fixtures/pii_eval.json')
    summary={'pending_export_blocked':True,'approved_export_succeeded':True,'tampered_export_blocked':True,
             'rejected_export_blocked':True,'evaluation':report['overall'],'scripted_review':scripted}
    (output/'demo-result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('RESULT:\n'+json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('demo-data'))
    p.add_argument('--scripted',action='store_true',help='Explicit synthetic review simulation for CI; no authenticated human review')
    args=p.parse_args()
    try:run(args.output,args.scripted)
    except (ValueError,OSError,UnicodeError,EOFError):
        p.exit(1,'Demo stopped; choose a new output directory and inspect the synthetic fixture.\n')
