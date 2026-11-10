import {request} from 'node:http';
import test from 'node:test';
import assert from 'node:assert/strict';
import {createApp} from '../server.mjs';
test('isolated HTTP API serves assets, rejects bad requests and completes a real config job',async()=>{
  const server=createApp();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=`http://127.0.0.1:${server.address().port}`;
  try{
    const home=await fetch(base);assert.equal(home.status,200);assert.match(await home.text(),/OrthoQuantum/);
    assert.equal((await fetch(base+'/api/health').then(r=>r.json())).implementation,'javascript-canvas');
    assert.equal((await fetch(base+'/bridge.py')).status,404);
    assert.equal((await fetch(base+'/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:'{'})).status,400);
    assert.equal((await fetch(base+'/api/jobs',{method:'POST',headers:{'Content-Type':'application/json',Origin:'https://unrelated.example'},body:'{}'})).status,403);
    assert.equal((await fetch(base+'/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"action":"delete"}'})).status,400);
    const started=await fetch(base+'/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"action":"config"}'}).then(r=>r.json());
    let result;for(let i=0;i<100;i++){result=await fetch(base+'/api/jobs/'+started.id).then(r=>r.json());if(['done','error'].includes(result.status))break;await new Promise(r=>setTimeout(r,30));}
    assert.equal(result.status,'done',result.error);assert.equal(result.data.trees.length,4);assert.equal(result.data.trees[0].species[0].id,'9606');
    const cached=await fetch(base+'/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"action":"config"}'}).then(r=>r.json());assert.equal(cached.id,started.id);assert.equal(cached.cached,true);
  }finally{server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}
});

test('configured public HTTP/HTTPS origins work behind a proxy while unrelated hosts/origins are rejected',async()=>{
  const server=createApp({publicOrigins:'http://orthoq.bioinf.fbb.msu.ru,https://orthoq.bioinf.fbb.msu.ru'});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`;
  const probe=headers=>new Promise((resolve,reject)=>{const req=request(base+'/api/health',{headers},res=>{res.resume();resolve(res.statusCode);});req.on('error',reject);req.end();});
  try{
    for(const origin of ['http://orthoq.bioinf.fbb.msu.ru','https://orthoq.bioinf.fbb.msu.ru']){
      assert.equal(await probe({Host:'orthoq.bioinf.fbb.msu.ru',Origin:origin}),200);
      assert.equal(await probe({Origin:origin}),200,'Proxy may rewrite Host to loopback');
    }
    assert.equal(await probe({Host:'unrelated.example'}),403);
    assert.equal(await probe({Host:'orthoq.bioinf.fbb.msu.ru',Origin:'https://unrelated.example'}),403);
  }finally{server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}
});
