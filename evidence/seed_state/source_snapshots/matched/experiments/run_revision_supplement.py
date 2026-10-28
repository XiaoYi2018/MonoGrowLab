"""Isolated validation-only supplementary runs; never append to archived experiments."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,platform,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import scipy,PIL,skimage
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'experiments'))
from monogrowlab.legacy_adapter import LegacyAdapter
from monogrowlab.datasets import load_bsds500_sample,resize_sample
from monogrowlab.evaluation import score_against_references,stability_scores
from monogrowlab.experiment_schema import canonical_hash,array_sha256
from monogrowlab.seed_controls import matched_bundles,seed_diagnostics,bundle_hash,validate_bundle
from run_bsds_robustness_v2 import normalize_corruption_specs,stable_seed,apply_corruption,RANDOM_FAMILIES,dataset_file_index,verified_dataset_hash

NOW=lambda:datetime.now(timezone.utc).isoformat()
def file_hash(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def write_new(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(json.dumps(data,indent=2,allow_nan=False)+'\n')
def append(p,data):
    with p.open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(data,sort_keys=True,allow_nan=False)+'\n');f.flush()
def result_metrics(result,refs):
    return {'seconds':result.seconds,'loops':result.loops,'threshold':result.threshold,'coverage':result.coverage,'regions':result.regions,**score_against_references(result.labels,refs)}
def execute(adapter,algorithm,seeds,image):
    validate_bundle(seeds)
    return adapter.run(algorithm['name'],seeds,image,eps=float(algorithm.get('eps',1.)),smooth_iters=int(algorithm.get('smooth_iters',0)),fan2015_l=float(algorithm.get('fan2015_l',15.)))
def evaluate_pair(adapter,algorithm,clean_image,corrupted_image,clean_seeds,recomputed_seeds,refs):
    # ONE matched-clean reference for BOTH corrupted branches. Preserve each source's initial state.
    reference=execute(adapter,algorithm,clean_seeds,clean_image)
    fixed=execute(adapter,algorithm,clean_seeds,corrupted_image)
    recomputed=execute(adapter,algorithm,recomputed_seeds,corrupted_image)
    rh=array_sha256(reference.labels)
    f={**result_metrics(fixed,refs),**stability_scores(reference.labels,fixed.labels)}
    r={**result_metrics(recomputed,refs),**stability_scores(reference.labels,recomputed.labels)}
    return {'fixed':f,'recomputed':r,'common_clean_labels_sha256':rh,'fixed_reference_sha256':rh,'recomputed_reference_sha256':rh,
            'matched_clean_seed_sha256':bundle_hash(clean_seeds),'matched_recomputed_seed_sha256':bundle_hash(recomputed_seeds),
            'matched_clean':result_metrics(reference,refs),**contrasts(f,r)}
def contrasts(f,r):
    return {'delta_stability_ari':f['stability_ari']-r['stability_ari'],
            'fixed_advantage_stability_vi_total':r['stability_vi_total']-f['stability_vi_total'],
            'delta_stability_boundary_f1_t1':f['stability_boundary_f1_t1']-r['stability_boundary_f1_t1'],
            'delta_gt_ari_mean':f['gt_ari_mean']-r['gt_ari_mean'],
            'fixed_advantage_gt_vi_total_mean':r['gt_vi_total_mean']-f['gt_vi_total_mean'],
            'delta_gt_boundary_f1_t1_mean':f['gt_boundary_f1_t1_mean']-r['gt_boundary_f1_t1_mean']}
def source_hashes():
    paths=[]
    for folder in ('src','experiments','legacy_reference/core','tests'):
        paths.extend((ROOT/folder).rglob('*.py'))
    return {p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(paths)}
def conditions(config,image_id,pilot=False):
    out=[]
    for spec in normalize_corruption_specs(config):
        for severity in spec['severities']:
            for replicate in range(spec['replicates']):
                fam,sid,params=spec['family'],severity['id'],severity['params']
                seed=stable_seed(spec['base_seed'],image_id,fam,sid,params,replicate) if fam in RANDOM_FAMILIES else None
                out.append({'corruption_family':fam,'severity_id':sid,'corruption_params':params,'replicate':replicate,'random_seed':seed})
    return out[:1] if pilot else out

def sensitivity_variants(base):
    out=[]
    for variant in base:
        for multiplier in (0.5,1.5):
            v=copy.deepcopy(variant);v['baseline_variant_id']=variant['id'];v['factor']='seed_sigma';v['factor_value']=float(variant['seed_strategy']['sigma'])*multiplier
            v['id']=variant['id']+'-sigma'+str(v['factor_value']).replace('.','p');v['seed_strategy']['sigma']=v['factor_value'];out.append(v)
    v0=next(v for v in base if v['algorithm']['name']=='clerg')
    for eps in (0.,2.):
        v=copy.deepcopy(v0);v['baseline_variant_id']=v0['id'];v['factor']='growth_eps';v['factor_value']=eps;v['algorithm']['eps']=eps;v['id']=v0['id']+'-eps'+str(int(eps));out.append(v)
    return out

def run(args):
    source_root=args.source_root.resolve();output=args.output_dir.resolve()
    if ROOT not in output.parents:raise ValueError('supplement output must be inside revision code directory')
    if source_root==ROOT or ROOT not in (source_root/'revisions').parents and source_root not in ROOT.parents:
        # Source must be an actual ancestor project, never an arbitrary filesystem root.
        raise ValueError('source-root must be the enclosing project directory')
    source_config=source_root/'configs/bsds500_multicorruption_v2_validation_10x160_r2.json'
    config=json.loads(source_config.read_text(encoding='utf-8-sig'))
    assert config['split']=='val' and len(config['image_ids'])==10 and len(config['variants'])==4
    ids=config['image_ids'][:1] if args.pilot else config['image_ids']
    variants=config['variants'] if args.kind=='matched' else sensitivity_variants(config['variants'])
    protocol={'supplement_schema_version':1,'analysis_role':'revision_added_secondary','kind':args.kind,'pilot':args.pilot,
              'source_config_sha256':file_hash(source_config),'source_config':config,'image_ids':ids,'variants':variants,
              'matched_draws':3,'match_type':'per-sign equal cardinality, independent seeded subsets without replacement',
              'reference':'one matched-clean reference shared by both matched branches',
              'spatial_diagnostic':'coordinate overlap, symmetric nearest distances, occupied 4x4 bins, within-3px area',
              'no_retuning':True,'no_heldout_run':True}
    psha=canonical_hash(protocol);sources=source_hashes()
    metadata={'protocol':protocol,'protocol_sha256':psha,'package_hashes':sources,'source_root':str(source_root),
              'revision_root':str(ROOT),'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
              'pillow':PIL.__version__,'skimage':skimage.__version__,'dataset_manifest_sha256':file_hash(source_root/config['dataset_manifest'])}
    meta_path=output/'metadata.json';record_path=output/'records.jsonl';diag_path=output/'seed_diagnostics.jsonl';done_path=output/'done.json'
    if done_path.exists():raise RuntimeError('Completed output is immutable; choose a new output directory')
    if meta_path.exists():
        if json.loads(meta_path.read_text())['immutable']!=metadata:raise RuntimeError('Refusing cross-version resume')
    else:
        if record_path.exists() or diag_path.exists():raise RuntimeError('Records exist without metadata')
        write_new(meta_path,{'created_utc':NOW(),'immutable':metadata})
    completed=set();diag_completed=set()
    for path,keys in ((record_path,completed),(diag_path,diag_completed)):
        if path.exists():
            for line in path.read_text().splitlines():
                record=json.loads(line);key=record['run_key']
                if key in keys or record.get('status')!='ok':raise RuntimeError('Duplicate/failed resume record')
                keys.add(key)
    manifest=json.loads((source_root/config['dataset_manifest']).read_text(encoding='utf-8-sig'))
    index,integrity=dataset_file_index(manifest,config['dataset_root']);dataset=source_root/config['dataset_root']
    # Exact official manifest input verification, including files outside selected validation subset.
    for relative,expected in index.items():
        p=dataset/relative
        if p.stat().st_size!=expected['bytes'] or file_hash(p)!=expected['sha256']:raise RuntimeError('Dataset integrity error: '+relative)
    integrity['scope']='all_manifest_files';print(json.dumps({'stage':'inputs_verified',**integrity}),flush=True)
    adapter=LegacyAdapter(ROOT/'legacy_reference/core');started=time.perf_counter();written=0;skipped=0
    try:
        for image_id in ids:
            sample=resize_sample(load_bsds500_sample(dataset,'val',image_id),config['max_dimension'])
            clean_image=adapter.to_gray_uint8(sample.image);ch=array_sha256(clean_image)
            ih=verified_dataset_hash(sample.image_path,dataset,index,'image');gh=verified_dataset_hash(sample.ground_truth_path,dataset,index,'ground_truth')
            conds=conditions(config,image_id,args.pilot)
            images={canonical_hash(c):apply_corruption(clean_image,c['corruption_family'],c['corruption_params'],seed=c['random_seed']) for c in conds}
            for variant in variants:
                clean_seeds=adapter.extract_seeds(clean_image,variant['seed_strategy']);validate_bundle(clean_seeds)
                base={'supplement_schema_version':1,'protocol_sha256':psha,'analysis_role':'revision_added_secondary','image_id':image_id,'variant_id':variant['id'],
                      'algorithm':variant['algorithm'],'seed_strategy':variant['seed_strategy'],'source_image_sha256':ih,'ground_truth_sha256':gh,'clean_image_sha256':ch}
                if args.kind=='sensitivity':
                    ci={**base,'mode':'clean','corruption_family':'clean','severity_id':'clean','replicate':0};key=canonical_hash(ci)
                    clean_result=execute(adapter,variant['algorithm'],clean_seeds,clean_image)
                    if key not in completed:
                        append(record_path,{**ci,'run_key':key,'status':'ok','created_utc':NOW(),'seed_count':clean_seeds.count,'labels_sha256':array_sha256(clean_result.labels),**result_metrics(clean_result,sample.references)})
                        completed.add(key);written+=1
                    else:skipped+=1
                for condition in conds:
                    corrupt=images[canonical_hash(condition)];rh=array_sha256(corrupt)
                    recomputed_seeds=adapter.extract_seeds(corrupt,variant['seed_strategy']);validate_bundle(recomputed_seeds)
                    identity={**base,**condition,'corrupted_image_sha256':rh}
                    if args.kind=='matched':
                        dk=canonical_hash({**identity,'mode':'seed_diagnostics'})
                        if dk not in diag_completed:
                            append(diag_path,{**identity,'run_key':dk,'status':'ok',**seed_diagnostics(clean_seeds,recomputed_seeds,corrupt)})
                            diag_completed.add(dk)
                        for draw in range(3):
                            key=canonical_hash({**identity,'draw':draw,'mode':'matched_pair'})
                            if key in completed:skipped+=1;continue
                            # Keys depend on full coordinates; draw seed is independent of segmentation outcomes.
                            draw_seed=int.from_bytes(hashlib.sha256((key+'|matched-cardinality').encode()).digest()[:8],'little')
                            ms,mr,selection=matched_bundles(clean_seeds,recomputed_seeds,draw_seed)
                            scores=evaluate_pair(adapter,variant['algorithm'],clean_image,corrupt,ms,mr,sample.references)
                            append(record_path,{**identity,'run_key':key,'status':'ok','created_utc':NOW(),'mode':'matched_pair','draw':draw,'selection_random_seed':draw_seed,'seed_count':ms.count,**selection,**scores})
                            completed.add(key);written+=1
                    else:
                        for mode,seeds in (('fixed_clean',clean_seeds),('recomputed',recomputed_seeds)):
                            key=canonical_hash({**identity,'mode':mode})
                            if key in completed:skipped+=1;continue
                            result=execute(adapter,variant['algorithm'],seeds,corrupt)
                            append(record_path,{**identity,'run_key':key,'status':'ok','created_utc':NOW(),'mode':mode,'baseline_variant_id':variant['baseline_variant_id'],
                                                'factor':variant['factor'],'factor_value':variant['factor_value'],'seed_count':seeds.count,
                                                'reference_labels_sha256':array_sha256(clean_result.labels),**result_metrics(result,sample.references),**stability_scores(clean_result.labels,result.labels)})
                            completed.add(key);written+=1
                print(json.dumps({'stage':'variant_complete','kind':args.kind,'image_id':image_id,'variant_id':variant['id'],'records':len(completed),'elapsed_seconds':time.perf_counter()-started}),flush=True)
        expected=sum(len(conditions(config,i,args.pilot)) for i in ids)*len(variants)*(3 if args.kind=='matched' else 2)+(len(ids)*len(variants) if args.kind=='sensitivity' else 0)
        if len(completed)!=expected:raise RuntimeError(f'Incomplete result grid: {len(completed)} vs {expected}')
        if source_hashes()!=sources:raise RuntimeError('Revision source changed during run')
        verdict={'status':'PASS','finished_utc':NOW(),'kind':args.kind,'pilot':args.pilot,'records':len(completed),'expected_records':expected,
                 'seed_diagnostic_records':len(diag_completed),'written':written,'skipped':skipped,'records_sha256':file_hash(record_path),
                 'metadata_sha256':file_hash(meta_path),'source_hashes_unchanged':True,'dataset_integrity':integrity,'elapsed_seconds':time.perf_counter()-started}
        if diag_path.exists():verdict['seed_diagnostics_sha256']=file_hash(diag_path)
        write_new(done_path,verdict);print(json.dumps(verdict),flush=True)
    except Exception as exc:
        failure={'status':'FAIL','time_utc':NOW(),'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()}
        failure_path=output/('failure-'+str(time.time_ns())+'.json');write_new(failure_path,failure);raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--kind',choices=['matched','sensitivity'],required=True);p.add_argument('--pilot',action='store_true');run(p.parse_args())
