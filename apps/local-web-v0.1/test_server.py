"""Safety and configuration tests; temporary evidence is retained, not deleted."""
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import server

class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=None
        if os.name=='nt':
            base=Path(tempfile.gettempdir())/'MonoGrowLab'/'web-tests'
            base.mkdir(parents=True,exist_ok=True)
        cls.root=Path(tempfile.mkdtemp(prefix='monogrow-web-test-',dir=base))
        for name in server.SCRIPTS.values():
            p=cls.root/'experiments'/name;p.parent.mkdir(exist_ok=True);p.write_text('')
        for split in ('train','val'):
            for iid in ('101','102'):
                for part,ext in [('images','.jpg'),('groundTruth','.mat')]:
                    p=cls.root/server.DATA/part/split/(iid+ext);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture')
        for rel in (server.MANIFEST,Path('legacy_reference/core/clerg_e.py')):
            p=cls.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
        print('Retained test fixtures: '+str(cls.root))
    def body(self):return {'split':'val','image_ids':['101','102'],'max_dimension':96,'variants':['clerg','adams'],'seed_policy':'strict','families':['gaussian_noise'],'replicates':2}
    def config(self,body=None):return server.make_config(self.root,body or self.body(),'run-20260919T120000-aabbccdd')
    def test_count_includes_clean(self):
        config,expected=self.config();self.assertEqual(expected,36)
        self.assertEqual([v['id'] for v in config['variants']],['clerg-strict','adams-strict'])
        self.assertEqual(config['seed_modes'],['fixed_clean','recomputed'])
    def test_deterministic_replicates(self):
        b=self.body();b['families']=['jpeg'];c,n=self.config(b)
        self.assertEqual(c['corruptions'][0]['replicates'],1);self.assertEqual(n,20)
    def test_invalid_fields(self):
        for key,value in [('output','../../paper/x'),('seed_modes',['fixed_clean']),('variants',['invalid']),('families',['invalid']),('split','test'),('max_dimension',16),('replicates',True),('image_ids',['101','101']),('seed_policy','unknown')]:
            b=self.body();b[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.config(b)
    def test_nonfinite_and_bounds(self):
        for v in (float('nan'),float('inf'),100000,True,'2'):
            b=self.body();b['severities']={'gaussian_noise':[v]}
            with self.subTest(v=v),self.assertRaises(ValueError):self.config(b)
    def test_traversal(self):
        for p in ('../x','/x','a/../../x','a//x','C:/Windows/x','a\\x','a/./x'):
            with self.subTest(p=p),self.assertRaises(ValueError):server.confined(self.root,p)
    def test_symlink_rejected(self):
        p=self.root/'linked'
        try:p.symlink_to(self.root/'experiments',target_is_directory=True)
        except OSError:self.skipTest('Symlink creation unavailable in test session')
        with self.assertRaises(ValueError):server.confined(self.root,'linked/run_bsds_robustness_v2.py')
    def test_one_active_job(self):
        w=server.Workbench(self.root)
        with patch.object(threading.Thread,'start'):
            first=w.start(self.body())
            with self.assertRaises(RuntimeError):w.start(self.body())
            self.assertEqual(w.active,first)
            self.assertEqual(w.describe(first)['minimum_p'],0.5)
        self.assertTrue((w.jobs_root/first/'config.json').is_file())

class HttpTests(ConfigTests):
    def test_http_boundaries(self):
        w=server.Workbench(self.root);service=server.Server(('127.0.0.1',0),w)
        thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
        port=service.server_port
        def request(method,path,body=None,headers=None):
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            conn.request(method,path,body,headers or {});r=conn.getresponse();result=(r.status,r.read());conn.close();return result
        try:
            self.assertEqual(request('GET','/api/health')[0],200)
            self.assertEqual(request('GET','/api/health',headers={'Host':'attacker.example'})[0],403)
            self.assertEqual(request('GET','/api/bootstrap',headers={'Origin':'https://attacker.example'})[0],403)
            self.assertEqual(request('POST','/api/jobs',b'{}',{'Content-Type':'application/json'})[0],403)
            h={'Content-Type':'application/json','X-MonoGrow-Token':w.token}
            self.assertEqual(request('POST','/api/jobs',b'{"split":"test"}',h)[0],400)
            self.assertEqual(request('POST','/api/jobs',b'{"replicates":NaN}',h)[0],400)
            self.assertEqual(request('GET','/api/image?split=test&id=101')[0],404)
            self.assertEqual(request('GET','/../paper/main.tex')[0],404)
        finally:service.shutdown();service.server_close()

if __name__=='__main__':unittest.main(verbosity=2)
