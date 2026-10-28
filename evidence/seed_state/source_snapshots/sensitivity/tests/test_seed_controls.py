"""Deterministic correctness tests for supplementary seed controls."""
import unittest
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"experiments"))
import numpy as np
from monogrowlab.legacy_adapter import SeedBundle
from monogrowlab.seed_controls import validate_bundle, subset_bundle, matched_bundles, bundle_hash, seed_diagnostics


def fixture(offset=0, short=False):
    coords = [(2,2),(2,5),(5,2),(5,5),(7,7)]
    signs = [1,1,-1,-1,-1]
    if short:
        coords, signs = coords[:3], signs[:3]
    m=np.zeros((10,10),dtype=np.int32)
    y=np.array([v[0] for v in coords],dtype=np.int32); x=np.array([v[1] for v in coords],dtype=np.int32)
    m[y,x]=np.array(signs)*np.arange(1,len(coords)+1)
    s=np.column_stack((np.ones(len(coords)),np.arange(len(coords))+offset)).astype(float)
    return SeedBundle(m,y,x,s,len(coords))

class ControlsTest(unittest.TestCase):
    def test_reindex_and_preserve_statistics(self):
        b=fixture();s=subset_bundle(b,np.array([4,0,2]));validate_bundle(s)
        np.testing.assert_array_equal(s.labels[s.y,s.x], [1,-2,-3])
        np.testing.assert_array_equal(s.statistics[:,1], [0,2,4])
    def test_match_types_and_source_state(self):
        a,b,selection=matched_bundles(fixture(10),fixture(80,True),123)
        self.assertEqual(a.count,b.count);self.assertEqual(selection['matched_type_counts'],{'maxima':2,'minima':1})
        self.assertTrue(np.all(a.statistics[:,1]<20));self.assertTrue(np.all(b.statistics[:,1]>=80))
    def test_determinism_and_no_input_mutation(self):
        a,b=fixture(),fixture(50,True);old=(bundle_hash(a),bundle_hash(b))
        one=matched_bundles(a,b,71);two=matched_bundles(a,b,71)
        self.assertEqual(bundle_hash(one[0]),bundle_hash(two[0]));self.assertEqual(one[2],two[2]);self.assertEqual(old,(bundle_hash(a),bundle_hash(b)))
    def test_label_identifier_validation(self):
        a=fixture();a.labels[a.y[1],a.x[1]]=77
        with self.assertRaises(ValueError):validate_bundle(a)
    def test_empty_is_rejected(self):
        a=SeedBundle(np.zeros((5,5),dtype=np.int32),np.array([],dtype=np.int32),np.array([],dtype=np.int32),np.zeros((0,2)),0)
        with self.assertRaises(ValueError):matched_bundles(a,fixture(),0)
    def test_distances_and_overlap(self):
        a=fixture();d=seed_diagnostics(a,a,np.zeros((10,10),dtype=np.uint8))
        self.assertEqual(d['coordinate_jaccard'],1);self.assertEqual(d['clean_same_type_retention'],1);self.assertEqual(d['symmetric_nearest_distance_px'],0)
    def test_both_branches_use_one_common_clean_reference(self):
        # The runner's paired evaluator must pass one immutable clean label map to both branches.
        from run_revision_supplement import evaluate_pair
        class Result:
            def __init__(self,labels):self.labels=labels;self.seconds=0.;self.loops=1;self.threshold=0.;self.coverage=1.;self.regions=2
        class Adapter:
            calls=[]
            def run(self,algorithm,seeds,image,**kwargs):
                self.calls.append((seeds,image.copy()));return Result((image>50).astype(int))
        a,b=fixture(),fixture(50,True);a,b,_=matched_bundles(a,b,2)
        clean=np.arange(100,dtype=np.uint8).reshape(10,10);corrupt=clean+2
        result=evaluate_pair(Adapter(),{'name':'clerg'},clean,corrupt,a,b,(clean>50,))
        self.assertIn('common_clean_labels_sha256',result);self.assertEqual(result['fixed_reference_sha256'],result['recomputed_reference_sha256'])

if __name__=='__main__':unittest.main()
