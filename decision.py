"""Local manual review and fail-closed export, not authenticated identity."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from integrity import loads, read_text


def verify_bundle(bundle):
    bundle = Path(bundle)
    manifest = loads(read_text(bundle / 'manifest.json'))
    if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int
            or manifest['schema_version'] != 1 or manifest.get('status') != 'pending_manual_review'
            or manifest.get('review_required') is not True):
        raise ValueError('Invalid pending review manifest')
    for key in ('source_sha256','sanitized_sha256'):
        if not isinstance(manifest.get(key),str) or not re.fullmatch('[a-f0-9]{64}',manifest[key]):
            raise ValueError('Invalid content digest')
    size, findings = manifest.get('characters'), manifest.get('findings')
    if type(size) is not int or not 0 <= size <= 1_000_000 or not isinstance(findings,list):
        raise ValueError('Invalid finding metadata')
    counts = Counter()
    last = 0
    for finding in findings:
        if (not isinstance(finding,dict) or set(finding) != {'kind','start','end'}
                or not isinstance(finding['kind'],str) or not re.fullmatch('[A-Z][A-Z0-9_]*',finding['kind'])
                or type(finding['start']) is not int or type(finding['end']) is not int
                or not last <= finding['start'] < finding['end'] <= size):
            raise ValueError('Invalid finding span')
        last = finding['end']; counts[finding['kind']] += 1
    declared = manifest.get('finding_counts')
    if (not isinstance(declared,dict) or any(type(x) is not int or x <= 0 for x in declared.values())
            or dict(counts) != declared):
        raise ValueError('Finding counts do not match spans')
    sanitized = read_text(bundle / 'sanitized.txt')
    if manifest['sanitized_sha256'] != hashlib.sha256(sanitized.encode('utf-8')).hexdigest():
        raise ValueError('Sanitized text differs from review manifest')
    return manifest, sanitized


def _write_exclusive(path, content):
    """Publish a complete private file without overwriting an existing path."""
    path=Path(path)
    fd, name=tempfile.mkstemp(prefix='.publish-',dir=path.parent)
    stage=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        # Link is an atomic no-clobber publication on the same filesystem.
        os.link(stage,path)
    finally:
        stage.unlink(missing_ok=True)


def manifest_digest(manifest):
    canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def decide(bundle,status,reviewer,rationale):
    if status not in ('approved','rejected'):
        raise ValueError('Decision must be approved or rejected')
    if not isinstance(reviewer,str) or not 1 <= len(reviewer.strip()) <= 128:
        raise ValueError('Reviewer must be 1..128 characters')
    if not isinstance(rationale,str) or not 1 <= len(rationale.strip()) <= 2000:
        raise ValueError('Rationale must be 1..2000 characters')
    manifest,_=verify_bundle(bundle)
    record={'schema_version':1,'status':status,'reviewer':reviewer.strip(),
            'rationale':rationale.strip(),'reviewed_at_utc':datetime.now(timezone.utc).isoformat(),
            'sanitized_sha256':manifest['sanitized_sha256'],'manifest_sha256':manifest_digest(manifest)}
    _write_exclusive(Path(bundle)/'decision.json',json.dumps(record,indent=2)+'\n')
    return record


def _verified_decision(bundle,manifest):
    record=loads(read_text(Path(bundle)/'decision.json'))
    if (not isinstance(record,dict) or type(record.get('schema_version')) is not int
            or record['schema_version'] != 1 or record.get('status') not in ('approved','rejected')
            or record.get('manifest_sha256') != manifest_digest(manifest)
            or record.get('sanitized_sha256') != manifest['sanitized_sha256']
            or not isinstance(record.get('reviewer'),str) or not 1 <= len(record['reviewer'].strip()) <= 128
            or not isinstance(record.get('rationale'),str) or not 1 <= len(record['rationale'].strip()) <= 2000
            or not isinstance(record.get('reviewed_at_utc'),str)):
        raise ValueError('Decision is invalid or no longer matches reviewed manifest')
    stamp=datetime.fromisoformat(record['reviewed_at_utc'])
    if stamp.tzinfo is None:
        raise ValueError('Review timestamp requires timezone')
    return record


def review_status(bundle):
    manifest,_=verify_bundle(bundle)
    try: record=_verified_decision(bundle,manifest)
    except FileNotFoundError:
        return {'status':'pending_manual_review','export_allowed':False}
    return {'status':record['status'],'export_allowed':record['status']=='approved'}


def export_approved(bundle,destination):
    # One validated snapshot supplies both the approval comparison and export bytes.
    manifest,sanitized=verify_bundle(bundle)
    decision=_verified_decision(bundle,manifest)
    if decision['status'] != 'approved':
        raise ValueError('Review has not approved export')
    _write_exclusive(destination,sanitized)
    return Path(destination)


def inspect_bundle(bundle,show_text=False):
    manifest,text=verify_bundle(bundle)
    result={'status':review_status(bundle),'finding_counts':manifest['finding_counts'],
            'findings':manifest['findings'],'characters':manifest['characters']}
    if show_text:result['sanitized_text']=text
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='command',required=True)
    for name in ('status','inspect'):
        sub=commands.add_parser(name);sub.add_argument('bundle',type=Path)
        if name=='inspect':sub.add_argument('--show-text',action='store_true',help='Explicitly print sanitized content; it can contain missed PII')
    review=commands.add_parser('decide');review.add_argument('bundle',type=Path)
    review.add_argument('--status',choices=('approved','rejected'),required=True)
    review.add_argument('--reviewer',required=True);review.add_argument('--rationale',required=True)
    release=commands.add_parser('export');release.add_argument('bundle',type=Path);release.add_argument('destination',type=Path)
    args=p.parse_args()
    try:
        if args.command=='status':result=review_status(args.bundle)
        elif args.command=='inspect':result=inspect_bundle(args.bundle,args.show_text)
        elif args.command=='decide':result={'status':decide(args.bundle,args.status,args.reviewer,args.rationale)['status']}
        else:
            export_approved(args.bundle,args.destination);result={'status':'exported'}
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,UnicodeError,RecursionError):
        p.exit(1,json.dumps({'error':{'code':'review_rejected','message':'Check bundle integrity, decision and destination'}})+'\n')
