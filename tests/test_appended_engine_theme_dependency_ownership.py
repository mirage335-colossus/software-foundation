"""Origin-preserving historical dependency export; synthetic reader fixtures.

Actual JSBase metadata evidence is retained separately in the isolated repair
packet; this test module opens no retained SDK or compiler.
"""
from pathlib import Path
import sys
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import appended_engine_document_maintenance as maintenance
import appended_engine_successful_donor as donor
import test_appended_engine_successful_donor as prior

class HistoricalDependencyOwnershipTests(unittest.TestCase):
    def fixture(self):
        return prior.NativeCapabilityAdmissionFixture(donor,maintenance)

    def test_opt_in_exports_verified_refs_for_both_compilation_origins(self):
        f=self.fixture()
        old=donor.native_capability_admission(f.reference,f.inspection,f.api)
        result=donor._native_repair_admission(f.reference,f.inspection,f.api,control_keypress=False,retain_dependencies=True)
        refs=result.pop('object_dependencies')
        self.assertEqual(old,result)
        self.assertNotIn('object_dependencies',old)
        self.assertEqual([r['id'] for r in result['objects']],list(refs))
        sidecar=f.api.documents[(f.sidecar_ref['path'],f.sidecar_ref['sha256'])]
        origins=set()
        for row in result['objects']:
            name=row['id'];origin=row['donor_provenance']['compile_origin'];origins.add(origin)
            self.assertTrue(refs[name])
            for ref in refs[name]:
                f.api.ref_path(ref,f.inspection.roots,f.inspection.inventories)
            if origin=='legacy-imported':
                self.assertEqual([sidecar['dependencies'][k]['input'] for k in row['dependency_keys']],refs[name])
            else:
                self.assertTrue(any(k not in sidecar['dependencies'] for k in row['dependency_keys']))
                self.assertIn(next(o['source'] for o in f.inspection.proof['objects'] if o['id']==name),refs[name])
        self.assertEqual({'legacy-imported','p5-compiled'},origins)

    def test_export_does_not_waive_current_dependency_or_original_fact_guards(self):
        for change in ('current','original'):
            f=self.fixture()
            if change=='current':f.inspection.inventories['sources']['units/main.cpp']='f'*64
            else:
                key=f.dependencies['main.cpp'][1]
                f.api.facts[key]['sha256']='f'*64
            with self.subTest(change=change),self.assertRaises(ValueError):
                donor._native_repair_admission(f.reference,f.inspection,f.api,control_keypress=False,retain_dependencies=True)

    def test_default_wrappers_keep_the_original_branch_and_new_wrapper_is_explicit(self):
        with mock.patch.object(donor,'_native_repair_admission',return_value={'inert':True}) as call:
            donor.native_control_keypress_admission('ref','inspection','api')
            self.assertEqual({'control_keypress':True},call.call_args.kwargs)
            donor.native_control_keypress_dependency_admission('ref','inspection','api')
            self.assertEqual({'control_keypress':True,'retain_dependencies':True},call.call_args.kwargs)
        with self.assertRaises(ValueError):
            donor._native_repair_admission(None,None,None,control_keypress=True,retain_dependencies=1)

if __name__=='__main__':unittest.main()
