"""Verify single-factor validation sensitivity and summarize image-level contrasts."""
from pathlib import Path
import argparse,csv,json,hashlib,collections,math,itertools
import numpy as np
METRICS={'delta_stability_ari':('stability_ari',1),'fixed_advantage_stability_vi_total':('stability_vi_total',-1),'delta_stability_boundary_f1_t1':('stability_boundary_f1_t1',1),'delta_gt_ari_mean':('gt_ari_mean',1),'fixed_advantage_gt_vi_total_mean':('gt_vi_total_mean',-1),'delta_gt_boundary_f1_t1_mean':('gt_boundary_f1_t1_mean',1)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def records(p):return [json.loads(l) for l in p.read_text(encoding='utf-8-sig').splitlines() if l]
def identity(r):return (r['image_id'],r['variant_id'],r['corruption_family'],r['severity_id'],r['replicate'])
def combine_pairs(rows,variant_key='variant_id',allow_undefined=False):
 clean={};pairs=collections.defaultdict(dict)
 for r in rows:
  assert r['status'] in ({'ok','no_seeds','no_clean_reference'} if allow_undefined else {'ok'})
  if r['status']=='no_seeds':assert r['seed_count']==0 and r.get('stability_ari') is None
  if r['status']=='no_clean_reference':assert r['mode']!='clean' and r.get('reference_labels_sha256') is None and r.get('stability_ari') is None
  if r['mode']=='clean':
   k=(r['image_id'],r[variant_key]);assert k not in clean;clean[k]=r
  else:
   k=(r['image_id'],r[variant_key],r['corruption_family'],r['severity_id'],r['replicate']);assert r['mode'] not in pairs[k];pairs[k][r['mode']]=r
 return clean,pairs

def average(rows,keys,fields):
 groups=collections.defaultdict(list)
 for r in rows:groups[tuple(r[k] for k in keys)].append(r)
 result=[]
 for k,rr in sorted(groups.items()):
  entry=dict(zip(keys,k))
  for field in fields:
   vals=[r[field] for r in rr];entry[field]=float(np.mean(vals)) if all(v is not None for v in vals) else None
  entry['defined']=all(r.get('defined',True) for r in rr)
  entry['undefined_conditions']=sum(r.get('undefined_conditions',int(not r.get('defined',True))) for r in rr)
  entry['total_conditions']=sum(r.get('total_conditions',1) for r in rr)
  result.append(entry)
 return result
def interval(vals,tag):
 x=np.asarray(vals,dtype=float);assert len(x)==10 and np.isfinite(x).all()
 seed=int.from_bytes(hashlib.sha256(('mgl-r1-sensitivity|'+tag).encode()).digest()[:8],'little')
 rng=np.random.default_rng(seed);samples=np.mean(x[rng.integers(0,len(x),size=(10000,len(x)))],axis=1)
 return [float(v) for v in np.quantile(samples,[.025,.975])]
def write_csv(path,rows):
 with path.open('x',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def analyze(args):
 root=args.sensitivity_dir;done=json.loads((root/'done.json').read_text());meta=json.loads((root/'metadata.json').read_text())['immutable'];p=meta['protocol'];cfg=p['source_config'];variants={v['id']:v for v in p['variants']};base_variants={v['id']:v for v in cfg['variants']}
 assert done['status']=='PASS' and done['records']==2900 and done['source_hashes_unchanged']
 assert p['kind']=='sensitivity' and p['pilot'] is False and p['no_retuning'] and p['no_heldout_run']
 assert p.get('undefined_contrast_policy') and done.get('grid_complete')

 assert sha(root/'records.jsonl')==done['records_sha256'] and sha(root/'metadata.json')==done['metadata_sha256']
 assert len(p['image_ids'])==10 and len(variants)==10 and len(base_variants)==4 and cfg['split']=='val'
 data=records(root/'records.jsonl');old=records(args.baseline_records)
 assert len(data)==2900 and len(old)==1160 and sha(args.baseline_records)=='f4739c52849a7ed4d8995c5ac1cd3d142ed722f2edd398493e64092555df824a'
 assert len({r['run_key'] for r in data})==2900
 validity_counts=dict(collections.Counter(r['status'] for r in data));assert done['validity_counts']==validity_counts
 for v in variants.values():
  base=base_variants[v['baseline_variant_id']]
  if v['factor']=='seed_sigma':
   assert v['algorithm']==base['algorithm'] and v['seed_strategy']['name']==base['seed_strategy']['name']
   assert v['factor_value']==v['seed_strategy']['sigma'] and v['factor_value']/base['seed_strategy']['sigma'] in (.5,1.5)
  else:
   assert v['factor']=='growth_eps' and v['seed_strategy']==base['seed_strategy'] and v['algorithm']['name']=='clerg'
   assert v['algorithm']['eps']==v['factor_value'] and v['factor_value'] in (0.,2.)
   assert {k:x for k,x in v['algorithm'].items() if k!='eps'}=={k:x for k,x in base['algorithm'].items() if k!='eps'}
 c,pairs=combine_pairs(data,allow_undefined=True);oc,op=combine_pairs(old);assert len(c)==100 and len(pairs)==1400 and len(oc)==40 and len(op)==560
 # Independent complete-grid reconstruction from the frozen configuration.
 coords=[]
 for image in p['image_ids']:
  for spec in cfg['corruptions']:
   for severity in spec['severities']:
    for replicate in range(spec['replicates']):coords.append((image,spec['family'],severity['id'],replicate))
 assert set(pairs)=={(i,v,f,s,r) for (i,f,s,r),v in itertools.product(coords,variants)}
 conditions=[]
 for source,pp in [('sensitivity',pairs),('baseline',op)]:
  for k,r in pp.items():
   assert set(r)=={'fixed_clean','recomputed'};fixed,recomputed=r['fixed_clean'],r['recomputed'];assert fixed['corrupted_image_sha256']==recomputed['corrupted_image_sha256']
   if source=='sensitivity':
    v=variants[k[1]];base_id=v['baseline_variant_id'];clean=c[(k[0],k[1])];reference=clean['labels_sha256']
    assert fixed['reference_labels_sha256']==recomputed['reference_labels_sha256']==reference
    assert fixed['seed_count']==clean['seed_count']
    if clean['status']=='no_seeds':
     assert clean['seed_count']==0 and reference is None and fixed['status']==recomputed['status']=='no_clean_reference'
    else:
     assert clean['status']=='ok' and reference and fixed['status']=='ok'
     assert recomputed['status'] in {'ok','no_seeds'}
    oldr=op[(k[0],base_id,k[2],k[3],k[4])]['fixed_clean'];assert fixed['corrupted_image_sha256']==oldr['corrupted_image_sha256']
   defined=fixed['status']==recomputed['status']=='ok'
   record={'source':source,'image_id':k[0],'variant':k[1],'family':k[2],'severity':k[3],'replicate':k[4],'defined':defined,'undefined_reason':'' if defined else fixed['status']+'|'+recomputed['status']}
   for metric,(field,direction) in METRICS.items():
    if defined:
     x=direction*(fixed[field]-recomputed[field]);assert math.isfinite(x);record[metric]=x
    else:record[metric]=None
   conditions.append(record)
 severity=average(conditions,['source','image_id','variant','family','severity'],list(METRICS))
 image=average(severity,['source','image_id','variant','family'],list(METRICS));assert len(image)==700
 groups=collections.defaultdict(list)
 for r in image:groups[(r['source'],r['variant'],r['family'])].append(r)
 with args.baseline_inference.open(encoding='utf-8-sig') as f:frozen_rows=list(csv.DictReader(f))
 frozen={(r['variant'],r['corruption_family'],r['metric']):r for r in frozen_rows if r['stratum']=='family'}
 family=[]
 for (source,variant,fam),rs in sorted(groups.items()):
  assert len(rs)==10
  for metric in METRICS:
   vals=[r[metric] for r in rs];defined=[v for v in vals if v is not None]
   if len(defined)==10:
    mean=float(np.mean(vals))
    if source=='baseline':
     archived=frozen[(variant,fam,metric)];assert abs(mean-float(archived['mean']))<1e-14
     mean=float(archived['mean']);lo,hi=float(archived['ci95_low']),float(archived['ci95_high'])
    else:lo,hi=interval(vals,variant+'|'+fam+'|'+metric)
   else:
    assert source=='sensitivity';mean=lo=hi=None
   family.append({'source':source,'variant':variant,'family':fam,'metric':metric,'n_images':10,'defined_images':len(defined),'mean':mean,'ci95_low':lo,'ci95_high':hi,'positive_images':sum(v>0 for v in defined),'negative_images':sum(v<0 for v in defined),'undefined_image_ids':','.join(r['image_id'] for r in rs if r[metric] is None)})
 lookup={(r['variant'],r['family'],r['metric']):r for r in family};axis=[]
 for baseline in base_variants.values():
  vv=[v for v in variants.values() if v['baseline_variant_id']==baseline['id'] and v['factor']=='seed_sigma']
  for v in [baseline,*vv]:
   for fam in {r['family'] for r in family}:
    r=lookup[(v['id'],fam,'delta_stability_ari')]
    axis.append({'algorithm':baseline['algorithm']['name'],'factor':'seed_sigma','value':v['seed_strategy']['sigma'],'baseline_variant':baseline['id'],**r})
 baseline=next(v for v in base_variants.values() if v['algorithm']['name']=='clerg')
 for v in [baseline,*[v for v in variants.values() if v['factor']=='growth_eps']]:
  for fam in {r['family'] for r in family}:
   r=lookup[(v['id'],fam,'delta_stability_ari')]
   axis.append({'algorithm':'clerg','factor':'growth_eps','value':float(v['algorithm']['eps']),'baseline_variant':baseline['id'],**r})
 axis.sort(key=lambda r:(r['factor'],r['algorithm'],r['family'],r['value']));assert len(axis)==75
 out=args.output_dir;out.mkdir(parents=True,exist_ok=False)
 for name,rs in [('condition_level.csv',conditions),('image_level.csv',image),('family_contrasts.csv',family),('parameter_axis_primary_ari.csv',axis)]:write_csv(out/name,rs)
 summary={'status':'PASS','new_records':2900,'clean_records':100,'new_pairs':1400,'new_variants':10,'baseline_records_reused':1160,'unique_family_groups':70,'image_level_rows':700,'parameter_axis_rows':75,'new_primary_tests':False,'analysis_role':'revision_added_secondary','bootstrap_iterations':10000,'no_retuning':True,'no_heldout_run':True,'validity_counts':validity_counts,'undefined_pairs':sum(not r['defined'] for r in conditions if r['source']=='sensitivity'),'fully_defined_new_family_groups':sum(r['source']=='sensitivity' and r['metric']=='delta_stability_ari' and r['defined_images']==10 for r in family),'undefined_policy':'No partial averaging: missing conditions propagate through severity/image; group means and CIs require all10 images.','inputs':{'sensitivity_sha256':sha(root/'records.jsonl'),'baseline_sha256':sha(args.baseline_records),'frozen_baseline_inference_sha256':sha(args.baseline_inference)}}
 (out/'verification.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
 text=['# Single-factor validation sensitivity','', 'Archived baseline effect estimates and confidence intervals are reused; only neighboring sigma/CLERG epsilon settings are new. All rows are secondary descriptions, not new primary tests or new selections.','', '| Algorithm | Factor | Family | Value | Defined images | Mean | 95% CI |','|---|---|---|---:|---:|---:|---|']
 for r in axis:
  mean=f"{r['mean']:+.4f}" if r['mean'] is not None else 'NA'
  ci=f"[{r['ci95_low']:+.4f}, {r['ci95_high']:+.4f}]" if r['ci95_low'] is not None else 'NA'
  text.append(f"| {r['algorithm']} | {r['factor']} | {r['family']} | {r['value']} | {r['defined_images']}/10 | {mean} | {ci} |")
 (out/'report.md').write_text('\n'.join(text)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sensitivity-dir',type=Path,required=True);p.add_argument('--baseline-records',type=Path,required=True);p.add_argument('--baseline-inference',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);analyze(p.parse_args())
