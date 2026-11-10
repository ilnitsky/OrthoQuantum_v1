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

test('full legacy About guide and all ten original pictures are served',async()=>{
 const server=createApp();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`;
 try{
  const response=await fetch(base+'/about');assert.equal(response.status,200);const html=await response.text();
  assert.match(html,/PantherDB Family\/Subfamily Classification Phyloprofile/);assert.match(html,/Input query details/);assert.match(html,/BLAST is currently unavailable/);
  assert.equal((html.match(/<img /g)||[]).length,10);assert.equal((await fetch(base+'/about/')).status,200);
  for(let i=1;i<=10;i++){const image=await fetch(base+`/tutorial/${i}.png`);assert.equal(image.status,200);assert.match(image.headers.get('content-type'),/image\/png/);const bytes=new Uint8Array(await image.arrayBuffer());assert.deepEqual([...bytes.slice(0,8)],[137,80,78,71,13,10,26,10]);}
 }finally{server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}
});

test('queued jobs have positions, active requests remain independent and summaries omit result data',async()=>{
 const {mkdtemp,writeFile,rm}=await import('node:fs/promises'),os=await import('node:os'),path=await import('node:path');
 const root=await mkdtemp(path.join(os.tmpdir(),'oq-queue-test-')),adapter=path.join(root,'adapter.py');
 await writeFile(adapter,'import json,sys,time\nr=json.load(sys.stdin)\ntime.sleep(0.8)\nprint(json.dumps({"type":"result","data":{"value":r.get("tag")}}),flush=True)\n');
 const server=createApp({adapterPath:adapter});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`;
 const start=async tag=>fetch(base+'/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'config',tag})}).then(r=>r.json());
 const get=async(id,summary=false)=>fetch(base+'/api/jobs/'+id+(summary?'?summary=1':'')).then(r=>r.json());
 try{
  const first=await start('queue-first');const duplicate=await start('queue-first');assert.notEqual(first.id,duplicate.id,'Running work must not be shared across query owners');
  assert.equal((await get(duplicate.id)).queuePosition,1);
  assert.equal((await fetch(base+'/api/jobs/'+duplicate.id,{method:'DELETE'}).then(r=>r.json())).status,'cancelled');
  const second=await start('queue-second');assert.equal((await get(second.id)).queuePosition,1,'Cancelled jobs do not occupy queue positions');
  assert.equal((await fetch(base+'/api/jobs')).status,404,'No global job-list endpoint');
  let result;for(let i=0;i<100;i++){result=await get(second.id);if(result.status==='done')break;await new Promise(resolve=>setTimeout(resolve,40));}
  assert.equal(result.status,'done');assert.equal(result.data.value,'queue-second');
  const summary=await get(second.id,true);assert.equal(summary.status,'done');assert.equal(summary.data,undefined);
 }finally{server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));await rm(root,{recursive:true,force:true});}
});
