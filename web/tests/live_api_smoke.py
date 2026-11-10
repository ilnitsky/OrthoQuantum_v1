"""Optional live read-only API checks; requires the prototype and upstream proxy."""
import json
import os
from pathlib import Path
import time
import urllib.request

BASE=os.environ.get('LITE_URL','http://127.0.0.1:8050')
OPEN=urllib.request.build_opener(urllib.request.ProxyHandler({}))


def job(request):
    body=json.dumps(request).encode()
    started=json.load(OPEN.open(urllib.request.Request(BASE+'/api/jobs',data=body,headers={'Content-Type':'application/json'}),timeout=15))
    deadline=time.monotonic()+190
    while time.monotonic()<deadline:
        state=json.load(OPEN.open(BASE+'/api/jobs/'+started['id'],timeout=15))
        if state['status']=='done':return state['data']
        if state['status'] in ('error','cancelled'):raise RuntimeError(state.get('error') or state['status'])
        time.sleep(.35)
    raise TimeoutError('Prototype job did not finish')


if __name__=='__main__':
    checks=[]
    for query in ['IPR003165','ko04210']:
        start=time.monotonic()
        result=job({'action':'resolve','inputs':query,'treeId':'1','taxid':'9606'})
        assert result['groups'],result
        assert result['release']=='v11'
        assert all(g['id'].endswith('at2759') for g in result['groups'])
        matrix=job({'action':'profiles','groups':result['groups'][:2],'treeId':'1','inputs':query,'title':'Online API smoke: '+query})
        assert len(matrix['species'])==165 and len(matrix['groups'])==2
        checks.append({'input':query,'matches':len(result['groups']),'builtGroups':2,'species':len(matrix['species']),'seconds':round(time.monotonic()-start,3),'warnings':result['warnings']})
        print(json.dumps(checks[-1]),flush=True)
    target=Path(__file__).parents[1]/'artifacts/online-api-results.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(checks,indent=2))
