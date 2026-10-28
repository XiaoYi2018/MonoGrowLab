"""Verify and summarize matched-cardinality supplementary results without changing archived inputs."""
from pathlib import Path
import csv,json,hashlib,math,itertools,collections
import numpy as np
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--matched-dir',type=Path,required=True)
parser.add_argument('--baseline-records',type=Path,required=True)
parser.add_argument('--baseline-inference',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args()
BASE=args.matched_dir
ORIGINAL=args.baseline_records
OUT=args.output_dir;OUT.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:[json.loads(l) for l in p.read_text(encoding='utf-8-sig').splitlines() if l]
done=json.loads((BASE/'done.json').read_text());metadata=json.loads((BASE/'metadata.json').read_text());protocol=metadata['immutable']['protocol'];cfg=protocol['source_config']
assert done['status']=='PASS' and done['source_hashes_unchanged']
for fn,key in [('records.jsonl','records_sha256'),('seed_diagnostics.jsonl','seed_diagnostics_sha256'),('metadata.json','metadata_sha256')]:assert sha(BASE/fn)==done[key],fn
rows=load(BASE/'records.jsonl');diags=load(BASE/'seed_diagnostics.jsonl');old=load(ORIGINAL)
assert len(rows)==1680 and len(diags)==560 and len(old)==1160
assert sha(ORIGINAL)=='f4739c52849a7ed4d8995c5ac1cd3d142ed722f2edd398493e64092555df824a'
assert len({r['run_key'] for r in rows})==1680 and all(r['status']=='ok' for r in rows+diags+old)
METRICS={'delta_stability_ari':('stability_ari',1),'fixed_advantage_stability_vi_total':('stability_vi_total',-1),'delta_stability_boundary_f1_t1':('stability_boundary_f1_t1',1),'delta_gt_ari_mean':('gt_ari_mean',1),'fixed_advantage_gt_vi_total_mean':('gt_vi_total_mean',-1),'delta_gt_boundary_f1_t1_mean':('gt_boundary_f1_t1_mean',1)}
key=lambda r:(r['image_id'],r['variant_id'],r['corruption_family'],r['severity_id'],r['replicate'])
matched=collections.defaultdict(list);diagnostic={key(r):r for r in diags};original=collections.defaultdict(dict)
for r in old:
 if r['mode']!='clean':
  k=key(r);assert r['mode'] not in original[k];original[k][r['mode']]=r
assert len(original)==560
for r in rows:
 assert r['draw'] in (0,1,2)
 assert r['common_clean_labels_sha256']==r['fixed_reference_sha256']==r['recomputed_reference_sha256']
 n=r['seed_count'];assert n==sum(r['matched_type_counts'].values())==len(r['selected_clean_indices'])==len(r['selected_recomputed_indices'])
 assert len(set(r['selected_clean_indices']))==len(set(r['selected_recomputed_indices']))==n
 for metric,(field,direction) in METRICS.items():
  v=direction*(r['fixed'][field]-r['recomputed'][field]);assert math.isclose(v,r[metric],abs_tol=1e-14),metric
 for side in ('fixed','recomputed'):
  assert 0<=r[side]['coverage']<=1 and -1.00000001<=r[side]['stability_ari']<=1.00000001
 matched[key(r)].append(r)
assert set(matched)==set(original)==set(diagnostic)
for k,v in matched.items():assert sorted(r['draw'] for r in v)==[0,1,2]
# Reconstruct the full grid independently from configuration.
expected=set()
for image,variant,c in itertools.product(cfg['image_ids'],cfg['variants'],cfg['corruptions']):
 for sev in c['severities']:
  for rep in range(c['replicates']):expected.add((image,variant['id'],c['family'],sev['id'],rep))
assert expected==set(matched)
# First average the fixed three draws within condition. Then replicate, severity, image.
condition=[]
for k,rr in matched.items():
 o=original[k];assert set(o)=={'fixed_clean','recomputed'}
 assert all(r['corrupted_image_sha256']==o['fixed_clean']['corrupted_image_sha256']==o['recomputed']['corrupted_image_sha256'] for r in rr)
 d=diagnostic[k]
 rec={'image_id':k[0],'variant':k[1],'family':k[2],'severity':k[3],'replicate':k[4]}
 for metric,(field,direction) in METRICS.items():
  rec['matched_'+metric]=float(np.mean([r[metric] for r in rr]));rec['original_'+metric]=direction*(o['fixed_clean'][field]-o['recomputed'][field])
 rec.update({'matched_seed_count':float(np.mean([r['seed_count'] for r in rr])),
             'clean_seed_count':d['clean']['count'],'recomputed_seed_count':d['recomputed']['count'],
             'coordinate_jaccard':d['coordinate_jaccard'],'same_type_retention':d['clean_same_type_retention'],
             'symmetric_nearest_distance_px':d['symmetric_nearest_distance_px'],
             'clean_occupied_4x4_fraction':d['clean']['occupied_4x4_fraction'],'recomputed_occupied_4x4_fraction':d['recomputed']['occupied_4x4_fraction'],
             'clean_within_3px_fraction':d['clean']['within_3px_fraction'],'recomputed_within_3px_fraction':d['recomputed']['within_3px_fraction'],
             'original_fixed_coverage':o['fixed_clean']['coverage'],'original_recomputed_coverage':o['recomputed']['coverage'],
             'matched_fixed_coverage':float(np.mean([r['fixed']['coverage'] for r in rr])),
             'matched_recomputed_coverage':float(np.mean([r['recomputed']['coverage'] for r in rr]))})
 condition.append(rec)
values=[k for k in condition[0] if k not in {'image_id','variant','family','severity','replicate'}]
def average(records,keys):
 groups=collections.defaultdict(list)
 for r in records:groups[tuple(r[k] for k in keys)].append(r)
 return [{**dict(zip(keys,k)),**{f:float(np.mean([r[f] for r in rr])) for f in values}} for k,rr in sorted(groups.items())]
severity=average(condition,['image_id','variant','family','severity'])
image=average(severity,['image_id','variant','family']);assert len(image)==200
fam=collections.defaultdict(list)
for r in image:fam[(r['variant'],r['family'])].append(r)
def ci(vals,tag):
 x=np.asarray(vals,dtype=float);assert np.isfinite(x).all()
 seed=int.from_bytes(hashlib.sha256(('mgl-r1-secondary|'+tag).encode()).digest()[:8],'little')
 rng=np.random.default_rng(seed);samples=np.mean(x[rng.integers(0,len(x),size=(10000,len(x)))],axis=1)
 return [float(v) for v in np.quantile(samples,[.025,.975])]
summary=[]
for (v,f),rr in sorted(fam.items()):
 assert len(rr)==10
 for metric in METRICS:
  xx=[r['matched_'+metric] for r in rr];oldx=[r['original_'+metric] for r in rr];lo,hi=ci(xx,v+'|'+f+'|'+metric)
  summary.append({'variant':v,'family':f,'metric':metric,'n_images':10,'original_mean':float(np.mean(oldx)),
                  'matched_mean':float(np.mean(xx)),'matched_ci95_low':lo,'matched_ci95_high':hi,
                  'matched_positive_images':sum(x>0 for x in xx),'matched_negative_images':sum(x<0 for x in xx)})
def write_csv(name,data):
 with (OUT/name).open('x',encoding='utf-8',newline='') as h:
  w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
write_csv('condition_level.csv',condition);write_csv('image_level.csv',image);write_csv('family_contrasts.csv',summary)
dsummary=average(image,['variant','family']);write_csv('seed_diagnostics_family.csv',dsummary)
# Compare the reconstructed ORIGINAL ARI estimates to archived inference, without changing it.
frozen=args.baseline_inference
with frozen.open(encoding='utf-8-sig') as h:frozen_rows=list(csv.DictReader(h))
lookup={(r['variant'],r['corruption_family']):float(r['mean']) for r in frozen_rows if r['stratum']=='family' and r['metric']=='delta_stability_ari'}
errors=[abs(r['original_mean']-lookup[(r['variant'],r['family'])]) for r in summary if r['metric']=='delta_stability_ari'];assert max(errors)<1e-14
report={'status':'PASS','records':1680,'seed_diagnostic_records':560,'condition_pairs':560,'draws_per_condition':3,'image_level_rows':200,
        'common_reference_mismatches':0,'contrast_recalculation_mismatches':0,'original_ari_reconstruction_max_error':max(errors),
        'bootstrap_iterations':10000,'analysis_role':'revision_added_secondary','new_primary_tests':False,
        'interpretation':'Matched-source sensitivity uses its own common clean reference. It is not a causal decomposition of the original gap; seed coordinates and initial intensities remain parts of the replaced state.',
        'inputs':{'matched_records_sha256':sha(BASE/'records.jsonl'),'diagnostics_sha256':sha(BASE/'seed_diagnostics.jsonl'),'baseline_records_sha256':sha(ORIGINAL)}}
(OUT/'verification.json').write_text(json.dumps(report,indent=2))
text=['# Matched-cardinality validation supplement','', 'Secondary analysis on the original ten validation images. No held-out re-run, new primary significance tests, or parameter selection.','', '| Variant | Family | Original mean gap | Matched mean gap | Matched 95% CI | Positive images / 10 |','|---|---|---:|---:|---|---:|']
for r in summary:
 if r['metric']=='delta_stability_ari':text.append(f"| {r['variant']} | {r['family']} | {r['original_mean']:+.4f} | {r['matched_mean']:+.4f} | [{r['matched_ci95_low']:+.4f}, {r['matched_ci95_high']:+.4f}] | {r['matched_positive_images']} |")
text+=['',report['interpretation'],'','Seed density/coordinates are summarized in seed_diagnostics_family.csv; nearest distances do not establish point identities.']
(OUT/'report.md').write_text('\n'.join(text)+'\n')
print(json.dumps(report,indent=2));print((OUT/'report.md').read_text())
