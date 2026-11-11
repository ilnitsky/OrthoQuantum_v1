"""Small metadata-only process; never loads reference databases or species trees."""
import json
import sys
from orthodb_stats import metadata
try:
    request=json.loads(sys.stdin.read(100000));print(json.dumps({'type':'result','data':metadata(request)}),flush=True)
except Exception as error:
    print(json.dumps({'type':'error','message':str(error)}),flush=True);sys.exit(1)
