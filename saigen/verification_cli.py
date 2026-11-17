"""CLI transport for verification; all integrity rules live in the service."""
import json
from pathlib import Path

from . import verification
from .records import RecordError


def register(command):
    parser=command('verify',help='Propose, approve, execute and compare a verification attempt')
    parser.add_argument('operation',choices=['propose','show','approve','execute','compare','recover','cancel'])
    parser.add_argument('--id',help='Verification proposal or attempt ID')
    parser.add_argument('--file',help='Proposal JSON file')
    parser.add_argument('--digest',help='Exact reviewed proposal digest')
    parser.add_argument('--revision',type=int)
    parser.add_argument('--reason',default='')


def dispatch(store,args):
    if args.operation=='show':return store.flow().get('verifications',{'proposals':{},'attempts':{}})
    if args.revision is None:raise RecordError('Supply --revision after inspecting the project')
    actor=args.actor or 'AI agent'
    if args.operation=='propose':
        if not args.file:raise RecordError('Supply --file')
        return verification.propose(store,json.loads(Path(args.file).read_text()),args.revision,actor)
    if not args.id:raise RecordError('Supply --id')
    if args.operation=='approve':return verification.approve(store,args.id,args.digest,args.revision,actor)
    if args.operation=='cancel':return verification.cancel(store,args.id,args.reason,args.revision,actor)
    return getattr(verification,args.operation)(store,args.id,args.revision,actor)
