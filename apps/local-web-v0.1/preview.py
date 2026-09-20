"""Render a verified illustrative pair using an interactive run's exact condition."""
import argparse
import json
from pathlib import Path
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project-root',type=Path,required=True)
    parser.add_argument('--job-id',required=True)
    args=parser.parse_args()
    from server import confined, JOB_ID
    if not JOB_ID.fullmatch(args.job_id):raise ValueError('Invalid job')
    root=args.project_root.resolve();job=confined(root,'ui_runs/'+args.job_id)
    config=json.loads((job/'config.json').read_text(encoding='utf-8'))
    sys.path.insert(0,str(root/'src'));sys.path.insert(0,str(root/'experiments'))
    import numpy as np
    from PIL import Image
    from monogrowlab.datasets import load_bsds500_sample,resize_sample
    from monogrowlab.legacy_adapter import LegacyAdapter
    from monogrowlab.metrics import boundary_map
    from monogrowlab.experiment_schema import array_sha256
    from monogrowlab.evaluation import stability_scores,score_against_references
    from monogrowlab.corruptions_v2 import apply_corruption
    from run_bsds_robustness_v2 import execute_algorithm
    rows=[json.loads(l) for l in (job/'run.jsonl').read_text().splitlines() if l]
    sample_record=next(r for r in rows if r['mode']=='fixed_clean')
    paired_record=next(r for r in rows if r['mode']=='recomputed' and
        all(r[k]==sample_record[k] for k in ('image_id','variant_id','corruption_family','severity_id','replicate')))
    variant=next(v for v in config['variants'] if v['id']==sample_record['variant_id'])
    sample=resize_sample(load_bsds500_sample(root/config['dataset_root'],config['split'],sample_record['image_id']),config['max_dimension'])
    adapter=LegacyAdapter(root/'legacy_reference'/'core')
    clean=adapter.to_gray_uint8(sample.image)
    corrupted=apply_corruption(clean,sample_record['corruption_family'],sample_record['corruption_params'],seed=sample_record['random_seed'])
    if array_sha256(clean)!=sample_record['clean_image_sha256'] or array_sha256(corrupted)!=sample_record['corrupted_image_sha256']:
        raise ValueError('Preview pixels do not match run evidence')
    seeds=adapter.extract_seeds(clean,variant['seed_strategy'])
    reseeds=adapter.extract_seeds(corrupted,variant['seed_strategy'])
    base=execute_algorithm(adapter,variant['algorithm'],seeds,clean)
    fixed=execute_algorithm(adapter,variant['algorithm'],seeds,corrupted)
    recomputed=execute_algorithm(adapter,variant['algorithm'],reseeds,corrupted)
    for result,record in ((fixed,sample_record),(recomputed,paired_record)):
        metrics={**stability_scores(base.labels,result.labels),**score_against_references(result.labels,sample.references)}
        if any(abs(metrics[k]-float(record[k]))>1e-10 for k in metrics):
            raise ValueError('Preview metrics differ from recorded condition')
    out=job/'preview';out.mkdir(exist_ok=False)
    context=f"{sample_record['image_id']} / {variant['id']} / {sample_record['corruption_family']} / {sample_record['severity_id']}"
    items=[]
    def save(name,label,pixels):
        file=name+'.png';Image.fromarray(pixels).save(out/file)
        items.append({'file':file,'label':label})
    def overlay(labels):
        rgb=np.repeat(corrupted[...,None],3,axis=2)
        rgb[boundary_map(labels)]=[15,185,155]
        return rgb.astype(np.uint8)
    save('clean','Clean input',clean)
    save('corrupted','Corrupted input',corrupted)
    save('fixed','Fixed clean seeds · boundaries',overlay(fixed.labels))
    save('recomputed','Recomputed seeds · boundaries',overlay(recomputed.labels))
    (out/'index.json').write_text(json.dumps(items,indent=2)+'\n',encoding='utf-8')
    (out/'evidence.json').write_text(json.dumps({'context':context,'recomputed_preview':True,
        'pixel_hashes_match':True,'metrics_match_tolerance':1e-10,
        'fixed_run_key':sample_record['run_key'],'recomputed_run_key':paired_record['run_key']},indent=2)+'\n')
    print('Preview verified against recorded pixel hashes and quality/stability metrics: '+context)

if __name__=='__main__':main()
