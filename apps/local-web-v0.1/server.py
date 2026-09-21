"""Loopback-only workbench around the unchanged MonoGrowLab experiment scripts."""
from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import hmac
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import webbrowser

APP = 'monogrowlab-local-web'
VERSION = '0.1.1'
HERE = Path(__file__).resolve().parent
JOB_ID = re.compile(r'run-\d{8}T\d{6}-[a-f0-9]{8}')
VARIANTS = {'clerg': ('CLERG', 'clerg', 1.0), 'adams': ('Adams', 'adams1994', 2.0),
            'fan2005': ('Fan2005', 'fan2005', 2.0), 'levelset': ('Level-set', 'levelset2004', 2.0)}
FAMILIES = {'gaussian_noise': ('Gaussian noise', [2., 8.], 0.1, 40.),
            'gaussian_blur': ('Gaussian blur', [0.5, 1.5], 0.1, 5.),
            'salt_pepper': ('Salt-and-pepper', [0.005, 0.02], 0.0001, 0.2),
            'jpeg': ('JPEG compression', [90, 50], 10, 100),
            'brightness_scale': ('Brightness scaling', [0.8, 1.2], 0.2, 2.)}
DATA = Path('data/raw/BSDS500_official_2013/BSR/BSDS500/data')
MANIFEST = Path('data/manifests/bsds500_official_2013_files_v2.json')
SCRIPTS = {'run':'run_bsds_robustness_v2.py', 'analyze':'analyze_attribution_v2.py',
           'summarize':'summarize_results_v2.py', 'report':'render_html_report_v2.py'}

def now():
    return datetime.now(timezone.utc).isoformat()

def confined(root: Path, relative: str, must_exist=False) -> Path:
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Invalid relative path')
    parts = relative.split('/')
    if any(p in {'', '.', '..'} for p in parts) or Path(relative).is_absolute():
        raise ValueError('Path traversal refused')
    base = root.resolve()
    current = base
    for part in parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ValueError('Linked paths are not served')
    path = current.resolve()
    if not path.is_relative_to(base) or path == base:
        raise ValueError('Path outside permitted root')
    if must_exist and not path.is_file():
        raise FileNotFoundError('File not available')
    return path

def finite_number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise ValueError('Expected a finite number')
    if not low <= value <= high:
        raise ValueError(f'Value must be between {low} and {high}')
    return value

def choice_list(value, choices, minimum=1, maximum=20):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f'Select between {minimum} and {maximum} items')
    if any(not isinstance(v,str) or v not in choices for v in value) or len(set(value)) != len(value):
        raise ValueError('Unknown or duplicate selection')
    return value

def image_ids(root, split):
    if not isinstance(split,str) or split not in {'train','val'}:
        raise ValueError('Select train or validation; held-out data are read-only')
    images=confined(root, (DATA/'images'/split).as_posix())
    truth=confined(root, (DATA/'groundTruth'/split).as_posix())
    return sorted(p.stem for p in images.glob('*.jpg') if p.stem.isdigit() and (truth/(p.stem+'.mat')).is_file())

def make_config(root: Path, body: dict, job_id: str):
    if not isinstance(body,dict): raise ValueError('Expected an object')
    allowed={'label','split','image_ids','max_dimension','variants','seed_policy','families','severities','replicates'}
    if set(body)-allowed: raise ValueError('Unknown configuration fields')
    if not JOB_ID.fullmatch(job_id): raise ValueError('Invalid job identifier')
    split=body.get('split','val')
    ids=choice_list(body.get('image_ids'), image_ids(root,split), 2,20)
    size=body.get('max_dimension',96)
    if type(size) is not int or size not in {64,96,128,160,256}: raise ValueError('Invalid image size')
    variants=choice_list(body.get('variants'),VARIANTS,1,4)
    families=choice_list(body.get('families'),FAMILIES,1,5)
    policy=body.get('seed_policy','gaussian')
    if not isinstance(policy,str) or policy not in {'gaussian','strict'}: raise ValueError('Unknown seed policy')
    repeats=body.get('replicates',2)
    if type(repeats) is not int or not 1<=repeats<=3: raise ValueError('Replicates must be 1 to 3')
    severity_map=body.get('severities',{})
    if not isinstance(severity_map,dict) or set(severity_map)-set(FAMILIES): raise ValueError('Unknown severity fields')
    algorithms=[]
    for key in variants:
        _, name, sigma=VARIANTS[key]
        algorithm={'name':name}
        if key=='clerg': algorithm.update(eps=1.0,smooth_iters=0)
        strategy={'name':'strict'} if policy=='strict' else {'name':'gaussian_strict','sigma':sigma}
        variant_id=key+('-strict' if policy=='strict' else f'-gaussian{sigma:g}')
        algorithms.append({'id':variant_id,'algorithm':algorithm,'seed_strategy':strategy})
    specs=[]
    for family in families:
        _, defaults, low, high=FAMILIES[family]
        values=severity_map.get(family,defaults)
        if not isinstance(values,list) or not 1<=len(values)<=2: raise ValueError('Choose one or two severity values')
        values=[finite_number(v,low,high) for v in values]
        if len(set(values))!=len(values): raise ValueError('Severity values must differ')
        severities=[]
        for number,value in enumerate(values):
            if family=='gaussian_noise': params={'sigma':value}
            elif family=='gaussian_blur': params={'sigma_px':value,'truncate':4.0,'boundary_mode':'reflect'}
            elif family=='salt_pepper': params={'amount':value,'salt_fraction':0.5,'sampling':'without_replacement'}
            elif family=='jpeg':
                if int(value)!=value: raise ValueError('JPEG quality must be an integer')
                params={'quality':int(value),'subsampling':0,'optimize':False,'progressive':False}
            else: params={'factor':value,'rounding':'nearest_even','clipping':'uint8_0_255'}
            severities.append({'id':f'level_{number+1}','params':params})
        specs.append({'family':family,'replicates':repeats if family in {'gaussian_noise','salt_pepper'} else 1,
                      'base_seed':20260919,'severities':severities})
    output=f'ui_runs/{job_id}/run.jsonl'
    path=confined(root,output)
    if not path.is_relative_to(confined(root,f'ui_runs/{job_id}')): raise ValueError('Output escapes job')
    config={'schema_version':2,'dataset_root':DATA.as_posix(),'dataset_manifest':MANIFEST.as_posix(),
            'split':split,'image_ids':ids,'max_dimension':size,'variants':algorithms,'corruptions':specs,
            'seed_modes':['fixed_clean','recomputed'],'analysis_role':'interactive_exploration',
            'interpretation':'User-configured exploratory evaluation; separate from frozen manuscript experiments.',
            'output':output}
    expected=len(ids)*len(algorithms)*(1+2*sum(len(s['severities'])*s['replicates'] for s in specs))
    return config,expected

def pid_alive(pid):
    if not pid: return False
    if os.name=='nt':
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,int(pid))
        if not handle: return ctypes.get_last_error()!=87
        try:
            code=wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value==259
        finally: kernel.CloseHandle(handle)
    return Path(f'/proc/{int(pid)}').exists()

class Workbench:
    def __init__(self,root:Path):
        self.root=root.resolve()
        if not all((self.root/'experiments'/n).is_file() for n in SCRIPTS.values()):
            raise ValueError('Not a MonoGrowLab source checkout')
        self.jobs_root=confined(self.root,'ui_runs')
        self.jobs_root.mkdir(exist_ok=True)
        self.lock=threading.Lock()
        self.active=None
        self.jobs={}
        self.token=secrets.token_urlsafe(32)
        for folder in sorted(self.jobs_root.iterdir()):
            if not JOB_ID.fullmatch(folder.name):continue
            try:
                journal=confined(self.jobs_root,folder.name+'/events.jsonl',True)
                states=[json.loads(l) for l in journal.read_text(encoding='utf-8').splitlines() if l]
                state=states[-1]
                if state['status'] in {'queued','running'}:
                    state.update(status='interrupted',error='Previous server stopped; no automatic restart. Partial files retained.')
                self.jobs[folder.name]=state
            except (OSError,ValueError,KeyError):continue

    def ready(self):
        required=[MANIFEST,Path('legacy_reference/core/clerg_e.py')]
        return all(confined(self.root,p.as_posix()).is_file() for p in required) and bool(image_ids(self.root,'val'))

    def update(self,jid,**change):
        with self.lock:
            self.jobs[jid].update(change,updated_at=now())
            state=dict(self.jobs[jid])
            path=confined(self.jobs_root,jid+'/events.jsonl')
            with path.open('a',encoding='utf-8') as h:
                h.write(json.dumps(state,ensure_ascii=True)+'\n');h.flush();os.fsync(h.fileno())

    def start(self,body):
        jid=datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%S-')+secrets.token_hex(4)
        config,expected=make_config(self.root,body,jid)
        label=body.get('label','Exploratory evaluation')
        if not isinstance(label,str) or len(label)>80 or any(ord(c)<32 for c in label):raise ValueError('Invalid label')
        if not self.ready():raise ValueError('Dataset manifest or growth kernels unavailable')
        with self.lock:
            if self.active or any(j['status']=='interrupted' and pid_alive(j.get('pid')) for j in self.jobs.values()):
                raise RuntimeError('Another evaluation is running; wait before starting a new one')
            folder=confined(self.jobs_root,jid);folder.mkdir(exist_ok=False)
            with (folder/'config.json').open('x',encoding='utf-8') as h:json.dump(config,h,indent=2)
            n=len(config['image_ids'])
            self.jobs[jid]={'id':jid,'label':label or 'Exploratory evaluation','status':'queued','stage':'Preparing',
                'created_at':now(),'records_written':0,'expected_records':expected,'n_images':n,
                'n_variants':len(config['variants']),'n_families':len(config['corruptions']),
                'minimum_p':2/(2**n) if n<=18 else 1/100001,'error':'','pid':None}
            self.active=jid
        self.update(jid,status='queued')
        threading.Thread(target=self.worker,args=(jid,config),daemon=False).start()
        return jid

    def execute(self,jid,stage,argv):
        folder=confined(self.jobs_root,jid)
        self.update(jid,status='running',stage=stage,pid=None)
        env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONUNBUFFERED']='1'
        env['MPLCONFIGDIR']=str(folder/'plot-cache')
        with (folder/(stage+'.log')).open('xb') as h:
            process=subprocess.Popen(argv,cwd=self.root,stdout=h,stderr=subprocess.STDOUT,env=env,shell=False)
            self.update(jid,pid=process.pid)
            code=process.wait()
        self.update(jid,pid=None,last_exit_code=code)
        if code:raise RuntimeError(f'{stage} failed (exit {code}); see the retained task log')

    def worker(self,jid,config):
        folder=confined(self.jobs_root,jid)
        py=sys.executable
        try:
            def script(name):return [py,'-u',str(self.root/'experiments'/SCRIPTS[name])]
            run=folder/'run.jsonl'
            self.execute(jid,'run',script('run')+['--config',str(folder/'config.json')])
            records=[json.loads(l) for l in run.read_text(encoding='utf-8').splitlines() if l]
            if len(records)!=self.jobs[jid]['expected_records'] or any(r.get('status')!='ok' for r in records):
                raise RuntimeError('Run integrity failed: wrong count or failed records')
            if len({r['run_key'] for r in records})!=len(records):raise RuntimeError('Duplicate run keys')
            args=script('analyze')+['--input',str(run),'--output-dir',str(folder/'analysis')]
            for v in config['variants']:args+=['--primary-variant',v['id']]
            self.execute(jid,'analyze',args)
            self.execute(jid,'summarize',script('summarize')+['--input',str(run),'--output-dir',str(folder/'summary')])
            self.execute(jid,'report',script('report')+['--analysis-dir',str(folder/'analysis'),
                          '--summary-dir',str(folder/'summary'),'--output',str(folder/'report.html')])
            preview_error=''
            try:self.execute(jid,'preview',[py,'-u',str(HERE/'preview.py'),'--project-root',str(self.root),'--job-id',jid])
            except Exception as exc:preview_error=str(exc)
            self.update(jid,status='complete',stage='Complete',records_written=len(records),preview_error=preview_error)
        except Exception as exc:self.update(jid,status='failed',stage='Failed',error=str(exc)[:400])
        finally:
            with self.lock:self.active=None

    def describe(self,jid,detail=False):
        with self.lock:state=dict(self.jobs[jid])
        folder=confined(self.jobs_root,jid)
        run=folder/'run.jsonl'
        if run.is_file():
            with run.open('rb') as h:state['records_written']=sum(line.endswith(b'\n') for line in h)
        state.update(report_url=None,downloads=[],results=[],preview=[])
        base='/artifacts/'+jid+'/'
        for name,label in [('config.json','Configuration'),('run.jsonl','Run records'),
                           ('analysis/inference.csv','Inference CSV'),('analysis/paired_records.csv','Paired CSV')]:
            if confined(folder,name).is_file():state['downloads'].append({'label':label,'url':base+name})
        if (folder/'report.html').is_file():state['report_url']=base+'report.html'
        inference=folder/'analysis'/'inference.csv'
        if inference.is_file():
            with inference.open(encoding='utf-8',newline='') as h:
                for r in csv.DictReader(h):
                    if r['stratum']=='family' and r['metric']=='delta_stability_ari':
                        state['results'].append({k:r[k] for k in ('variant','corruption_family','mean','ci95_low','ci95_high','holm_p')})
        preview=folder/'preview'/'index.json'
        if preview.is_file():
            state['preview']=[{'label':r['label'],'url':base+'preview/'+r['file']} for r in json.loads(preview.read_text())]
        if detail:
            logs=[]
            for stage in ('run','analyze','summarize','report','preview'):
                path=folder/(stage+'.log')
                if path.is_file():
                    with path.open('rb') as h:
                        h.seek(max(0,path.stat().st_size-6000));logs.append(stage+'\n'+h.read().decode('utf-8','replace'))
            state['log_tail']='\n'.join(logs)[-12000:]
        state.pop('pid',None)
        return state

    def frozen_reports(self):
        base=self.root/'reports'/'generated'
        candidates=sorted(base.glob('*report*.html'))
        wanted=[p for p in candidates if 'test_200x160_r1' in p.name or 'validation_10x160_r2' in p.name or 'strict_sensitivity_r1' in p.name]
        return {str(i):p for i,p in enumerate(wanted)}

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,workbench):
        self.workbench=workbench;self.gate=threading.BoundedSemaphore(16)
        super().__init__(address,Handler)
    def process_request(self,request,client_address):
        if not self.gate.acquire(blocking=False):self.shutdown_request(request);return
        try:super().process_request(request,client_address)
        except BaseException:self.gate.release();raise
    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self.gate.release()

class Handler(BaseHTTPRequestHandler):
    server_version='MonoGrowLab/0.1'
    def log_message(self,*args):pass
    def setup(self):
        super().setup();self.connection.settimeout(15)
    def allowed_host(self):
        port=self.server.server_port
        allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
        origin=self.headers.get('Origin')
        return self.headers.get('Host') in allowed and (not origin or origin in {'http://'+h for h in allowed})
    def send(self,data,status=200,ctype='application/json; charset=utf-8',sandbox=False):
        if isinstance(data,(dict,list)):data=json.dumps(data,allow_nan=False).encode()
        elif isinstance(data,str):data=data.encode()
        self.send_response(status);self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        csp="sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:" if sandbox else "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
        self.send_header('Content-Security-Policy',csp);self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if not self.allowed_host():return self.send({'error':'Host or Origin rejected'},403)
        w=self.server.workbench
        parsed=urlsplit(self.path);path=unquote(parsed.path)
        try:
            if path=='/api/health':return self.send({'app':APP,'version':VERSION,'project_id':hashlib.sha256(str(w.root).encode()).hexdigest()[:16]})
            if path=='/api/bootstrap':
                reports=[{'id':i,'label':p.stem,'url':'/frozen/'+i} for i,p in w.frozen_reports().items()]
                return self.send({'token':w.token,'ready':w.ready(),'message':'Ready' if w.ready() else 'Dataset or kernels unavailable',
                    'version':VERSION,'images':{s:image_ids(w.root,s) for s in ('train','val')},
                    'variants':[{'id':k,'label':v[0]} for k,v in VARIANTS.items()],
                    'families':[{'id':k,'label':v[0]} for k,v in FAMILIES.items()],'frozen_reports':reports})
            if path=='/api/jobs':
                with w.lock:ids=sorted(w.jobs,reverse=True)[:50]
                return self.send({'jobs':[w.describe(i) for i in ids]})
            if path.startswith('/api/jobs/'):
                jid=path.split('/')[-1]
                if not JOB_ID.fullmatch(jid) or jid not in w.jobs:raise FileNotFoundError()
                return self.send(w.describe(jid,True))
            if path=='/api/image':
                q=parse_qs(parsed.query,strict_parsing=True);split=q.get('split',[''])[0];iid=q.get('id',[''])[0]
                if split not in {'train','val'} or not re.fullmatch(r'\d{1,12}',iid):raise ValueError('Invalid image')
                target=confined(w.root,(DATA/'images'/split/(iid+'.jpg')).as_posix(),True)
                return self.send(target.read_bytes(),ctype='image/jpeg')
            if path.startswith('/frozen/'):
                target=w.frozen_reports().get(path.split('/')[-1])
                if target is None:raise FileNotFoundError()
                return self.send(target.read_bytes(),ctype='text/html; charset=utf-8',sandbox=True)
            if path.startswith('/artifacts/'):
                parts=path.split('/',3)
                if len(parts)!=4 or not JOB_ID.fullmatch(parts[2]) or parts[2] not in w.jobs:raise ValueError('Invalid artifact')
                relative=parts[3]
                if not (relative in {'config.json','run.jsonl','run.jsonl.meta.json','report.html'} or
                        re.fullmatch(r'analysis/[a-z_]+\.(csv|json|md)',relative) or
                        re.fullmatch(r'preview/[a-z0-9_-]+\.png',relative)):
                    raise ValueError('Artifact type not exposed')
                target=confined(w.jobs_root,parts[2]+'/'+relative,True)
                mime=mimetypes.guess_type(target.name)[0] or 'text/plain'
                return self.send(target.read_bytes(),ctype=mime,sandbox=target.suffix=='.html')
            assets={'/':'index.html','/index.html':'index.html','/app.css':'app.css','/app.js':'app.js'}
            if path not in assets:raise FileNotFoundError()
            target=HERE/assets[path]
            return self.send(target.read_bytes(),ctype=mimetypes.guess_type(target.name)[0] or 'text/plain')
        except (ValueError,KeyError,FileNotFoundError):self.send({'error':'Resource not available or invalid request'},404)
        except OSError:self.send({'error':'Cannot read requested resource'},500)
    def do_POST(self):
        if not self.allowed_host():return self.send({'error':'Host or Origin rejected'},403)
        w=self.server.workbench
        if not hmac.compare_digest(self.headers.get('X-MonoGrow-Token',''),w.token):return self.send({'error':'Invalid request token; reload the page'},403)
        if self.path!='/api/jobs':return self.send({'error':'Unknown action'},404)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if self.headers.get('Transfer-Encoding') or not 0<size<=32768:raise ValueError('Invalid request size')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Expected application/json')
            def reject_constant(x):raise ValueError('Nonfinite JSON number')
            body=json.loads(self.rfile.read(size),parse_constant=reject_constant)
            jid=w.start(body);self.send({'job_id':jid},201)
        except (ValueError,RecursionError,UnicodeError) as exc:self.send({'error':str(exc)[:200]},400)
        except RuntimeError as exc:self.send({'error':str(exc)},409)
        except OSError:self.send({'error':'Unable to create task; files retained'},500)

def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,default=HERE.parents[1])
    p.add_argument('--port',type=int,default=8767);p.add_argument('--open-browser',action='store_true')
    args=p.parse_args();w=Workbench(args.project_root);server=Server(('127.0.0.1',args.port),w)
    url=f'http://127.0.0.1:{server.server_port}/'
    print(f'MonoGrowLab workbench: {url}',flush=True)
    print('Closing a browser tab leaves evaluation running. Keep this console open.',flush=True)
    if args.open_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:print('Server stopped. Task files are retained.',flush=True)
    finally:server.server_close()

if __name__=='__main__':main()
