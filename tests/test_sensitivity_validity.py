"""Empty seed states are explicit observations, not zero-valued predictions."""
from pathlib import Path
import sys,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
for directory in ('src','experiments','tests'):sys.path.insert(0,str(ROOT/directory))
from monogrowlab.legacy_adapter import SeedBundle
from monogrowlab.seed_controls import classify_seed_bundle,sensitivity_seed_status
from run_revision_supplement import sensitivity_metrics
from test_seed_controls import fixture

def empty():return SeedBundle(np.zeros((10,10),dtype=np.int32),np.empty(0,dtype=np.int32),np.empty(0,dtype=np.int32),np.empty((0,2)),0)
class NoGrowth:
    def run(self,*args,**kwargs):raise AssertionError('Growth must not be called for an unavailable comparison')
class Reference:
    labels=np.zeros((10,10),dtype=np.int64)
class ValidityTest(unittest.TestCase):
    def test_explicit_empty(self):
        self.assertEqual(classify_seed_bundle(empty()),'empty');self.assertEqual(classify_seed_bundle(fixture()),'ready')
    def test_malformed_empty_is_error(self):
        b=empty();b.labels[2,2]=1
        with self.assertRaisesRegex(ValueError,'malformed'):classify_seed_bundle(b)
    def test_no_clean_reference_no_fake_metrics(self):
        out=sensitivity_metrics(NoGrowth(),{'name':'clerg'},None,empty(),fixture(),np.zeros((10,10)),(np.zeros((10,10)),))
        self.assertEqual(out['status'],'no_clean_reference');self.assertIsNone(out['reference_labels_sha256']);self.assertIsNone(out['stability_ari']);self.assertIsNone(out['coverage']);self.assertIsNone(out['gt_ari_mean'])
    def test_empty_candidate_keeps_actual_reference(self):
        out=sensitivity_metrics(NoGrowth(),{'name':'clerg'},Reference(),fixture(),empty(),np.zeros((10,10)),(np.zeros((10,10)),))
        self.assertEqual(out['status'],'no_seeds');self.assertIsNotNone(out['reference_labels_sha256']);self.assertIsNone(out['stability_ari']);self.assertIsNone(out['regions'])
    def test_unexpected_missing_reference_remains_error(self):
        with self.assertRaisesRegex(RuntimeError,'nonempty clean'):sensitivity_metrics(NoGrowth(),{'name':'clerg'},None,fixture(),fixture(),np.zeros((10,10)),())
    def test_status_preserves_empty_vs_reference_distinction(self):
        self.assertEqual(sensitivity_seed_status(empty(),empty()),'no_clean_reference');self.assertEqual(sensitivity_seed_status(fixture(),empty()),'no_seeds');self.assertEqual(sensitivity_seed_status(fixture(),fixture()),'ok')
if __name__=='__main__':unittest.main()
