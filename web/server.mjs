import http from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {randomUUID, createHash} from 'node:crypto';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(ROOT, 'public');
const MIME = {'.html':'text/html; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.ttf':'font/ttf','.ico':'image/x-icon','.png':'image/png','.txt':'text/plain; charset=utf-8','.tsv':'text/tab-separated-values; charset=utf-8'};
const jobs = new Map();
const queue = [];
const metadataQueue = [];
let activeMetadata=false;
let active = false;
const MAX_JOBS = 15;
const MAX_BODY = 10_000_000;
const MAX_OUTPUT = 50_000_000;

function send(res, status, body) {
  res.writeHead(status, {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});
  res.end(JSON.stringify(body));
}
function cleanup(metadata=false) {
  const matches=job=>(job.request.action==='metadata')===metadata;
  for (const [id, job] of jobs) {
    if (['done','error','cancelled'].includes(job.status) && Date.now()-job.updated > 3600_000) jobs.delete(id);
  }
  while ([...jobs.values()].filter(matches).length >= MAX_JOBS) {
    const expired = [...jobs.values()].find(j => matches(j)&&['done','error','cancelled'].includes(j.status));
    if (!expired) break;
    jobs.delete(expired.id);
  }
}
async function runNext(metadata=false) {
  const pendingJobs=metadata?metadataQueue:queue;
  if ((metadata?activeMetadata:active) || !pendingJobs.length) return;
  const job=pendingJobs.shift();
  if(job.status==='cancelled')return runNext(metadata);
  if(metadata)activeMetadata=true;else active=true;
  job.status = 'running'; job.updated = Date.now();
  const child = spawn(process.env.PYTHON || 'python3', [job.adapterPath||path.join(ROOT, 'bridge.py')], {
    cwd: ROOT, env: process.env, stdio: ['pipe','pipe','pipe'],
  });
  job.child = child;
  let pending = '', total = 0, errors = '', finished = false;
  const timer = setTimeout(() => {job.error = 'Query exceeded the 15-minute job budget.'; child.kill();}, 900_000);
  child.stdout.on('data', chunk => {
    total += chunk.length;
    if (total > MAX_OUTPUT) {job.error = 'Result exceeds the dataset size limit.'; child.kill(); return;}
    pending += chunk.toString();
    let end;
    while ((end=pending.indexOf('\n'))>=0) {
      const line = pending.slice(0,end); pending = pending.slice(end+1);
      try {
        const event = JSON.parse(line);
        if (event.type === 'progress') job.progress = event;
        if (event.type === 'result') {job.result = event.data; finished = true;}
        if (event.type === 'error') job.error = event.message;
        job.updated = Date.now();
      } catch {job.error = 'Invalid response from the reference-data adapter.'; child.kill();}
    }
  });
  child.stderr.on('data', chunk => {if (errors.length < 2000) errors += chunk.toString();});
  child.on('error', error => {job.error = `Cannot start Python adapter: ${error.message}`;});
  child.on('close', code => {
    clearTimeout(timer); delete job.child;
    if (job.status !== 'cancelled') job.status = code === 0 && finished && !job.error ? 'done' : 'error';
    if (job.status === 'error' && !job.error) job.error = errors || 'Reference-data job failed.';
    job.updated = Date.now(); if(metadata)activeMetadata=false;else active=false;runNext(metadata);
  });
  child.stdin.on('error', () => {});
  child.stdin.end(JSON.stringify(job.request));
}
export function createApp({publicOrigins=process.env.PUBLIC_ORIGINS||'',adapterPath=path.join(ROOT,'bridge.py'),metadataAdapterPath=path.join(ROOT,'metadata_adapter.py')}={}) {
  const origins=new Set(publicOrigins.split(',').map(v=>v.trim()).filter(Boolean).map(value=>{
    const url=new URL(value);if(!['http:','https:'].includes(url.protocol))throw new Error('PUBLIC_ORIGINS must contain HTTP(S) origins');return url.origin;
  }));
  const publicHosts=new Set([...origins].map(value=>new URL(value).hostname));
  return http.createServer(async (req,res) => {
    res.setHeader('X-Content-Type-Options','nosniff');
    res.setHeader('Referrer-Policy','no-referrer');
    res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
    try {
      const url = new URL(req.url, 'http://localhost');
      const hostname = new URL(`http://${req.headers.host || 'invalid'}`).hostname;
      const local=['localhost','127.0.0.1','[::1]'].includes(hostname);
      if (!local&&!publicHosts.has(hostname)) return send(res,403,{error:'Unknown site host.'});
      if (req.headers.origin&&!origins.has(req.headers.origin)&&!(local&&req.headers.origin===`http://${req.headers.host}`)) return send(res,403,{error:'Use OrthoQuantum from its own origin.'});
      if (url.pathname === '/api/health') return send(res,200,{status:'ok',application:'orthoquantum',implementation:'javascript-canvas',activeJobs:Number(active)+Number(activeMetadata),analysisJobs:Number(active),metadataJobs:Number(activeMetadata)});
      if (url.pathname === '/api/jobs' && req.method === 'POST') {
        if (!String(req.headers['content-type']).startsWith('application/json')) return send(res,415,{error:'JSON required'});
        let raw='';req.setEncoding('utf8');
        for await (const chunk of req) {
          raw += chunk.toString();
          if (raw.length > MAX_BODY) return send(res,413,{error:'Request too large'});
        }
        const body = JSON.parse(raw);
        if (!body || typeof body !== 'object' || Array.isArray(body)) return send(res,400,{error:'Expected a query object'});
        if (!['resolve','profiles','config','panther','panther_orthologs','metadata'].includes(body.action)) return send(res,400,{error:'Unknown query action'});
        cleanup(body.action==='metadata');
        if ([...jobs.values()].filter(j=>(j.request.action==='metadata')===(body.action==='metadata')).length >= MAX_JOBS) return send(res,429,{error:'Job queue is full. Wait for a job to finish.'});
        // In-memory cache is bounded and invalidates when reference files change.
        const versions = await Promise.all([
          ...['trees-v13.json','trees-timetree-v13.json'].map(name=>path.join(PUBLIC,'data',name)),
          process.env.ORTHODB_PATH || '/home/ilnitsky/PANTHERDB/orthodb.db',
          ...(process.env.ORTHODB_LEVELS_PATH ? [process.env.ORTHODB_LEVELS_PATH,process.env.ORTHODB_LEVELS_PATH+'.json'] : []),
          process.env.PANTHER_PATH || '/home/ilnitsky/PANTHERDB/panther.sqlite',
          ...(process.env.PANTHER_BUNDLE_DIR ? ['manifest.json','panther.sqlite','relationships.sqlite'].map(name=>path.join(process.env.PANTHER_BUNDLE_DIR,name)) : []),
        ].map(async p => {try {const s=await stat(p);return [s.ino,s.size,s.mtimeMs];} catch {return null;}}));
        const key = createHash('sha256').update(JSON.stringify([body,versions,process.env.ORTHODB_RELEASE || 'v11'])).digest('hex');
        const existing=[...jobs.values()].find(j=>j.key===key && j.status==='done' && !(body.action==='metadata'&&Object.keys(j.result?.errors||{}).length));
        if(existing) return send(res,202,{id:existing.id,cached:existing.status==='done'});
        const id=randomUUID();
        const job={id,key,adapterPath:body.action==='metadata'?metadataAdapterPath:adapterPath,request:body,status:'queued',updated:Date.now(),progress:{message:'Waiting for the reference database'}};
        jobs.set(id,job);const isMetadata=body.action==='metadata';(isMetadata?metadataQueue:queue).push(job);runNext(isMetadata);return send(res,202,{id});
      }
      const match=/^\/api\/jobs\/([0-9a-f-]+)$/.exec(url.pathname);
      if (match) {
        const job=jobs.get(match[1]);
        if(!job) return send(res,404,{error:'Job has expired. Submit the query again.'});
        if(req.method==='DELETE') {
          if(job.status==='queued' || job.status==='running') {job.status='cancelled';job.child?.kill();job.updated=Date.now();}
          return send(res,200,{status:job.status});
        }
        if(req.method!=='GET') return send(res,405,{error:'Method not allowed'});
        const queuePosition=job.status==='queued'?(job.request.action==='metadata'?metadataQueue:queue).filter(j=>j.status==='queued').indexOf(job)+1:job.status==='running'?0:undefined;
        return send(res,200,{id:job.id,status:job.status,queuePosition,progress:job.progress,error:job.error,data:job.status==='done'&&!url.searchParams.has('summary')?job.result:undefined});
      }
      if(url.pathname.startsWith('/api/')) return send(res,404,{error:'Unknown endpoint'});
      if(!['GET','HEAD'].includes(req.method)) return send(res,405,{error:'Method not allowed'});
      const name = url.pathname==='/' ? 'index.html' : ['/about','/about/'].includes(url.pathname)?'about.html': decodeURIComponent(url.pathname).replace(/^\/+/, '');
      const filename = path.resolve(PUBLIC,name);
      if(!filename.startsWith(PUBLIC+path.sep) || !MIME[path.extname(filename)]) return send(res,404,{error:'Not found'});
      const info=await stat(filename);
      if(!info.isFile()) return send(res,404,{error:'Not found'});
      const etag=`"${info.size}-${Math.trunc(info.mtimeMs)}"`;
      if(req.headers['if-none-match']===etag) {res.writeHead(304);return res.end();}
      res.writeHead(200, {'Content-Type':MIME[path.extname(filename)],'Content-Length':info.size,'ETag':etag,'Cache-Control':path.extname(filename)==='.ttf'?'public, max-age=604800':'no-cache'});
      if(req.method==='HEAD') return res.end();
      createReadStream(filename).pipe(res);
    } catch(error) {send(res,error instanceof SyntaxError?400:error.code==='ENOENT'?404:500,{error:error instanceof SyntaxError?'Invalid JSON':error.code==='ENOENT'?'Not found':'Prototype request failed.'});}
  });
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const host=process.env.HOST || '127.0.0.1',port=Number(process.env.PORT || 8051);
  const server=createApp();
  server.listen(port,host,()=>console.log(`OrthoQuantum Lite: http://${host}:${port} (isolated experiment)`));
  for(const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>{for(const job of jobs.values()) job.child?.kill(); server.close(()=>process.exit(0));});
}
