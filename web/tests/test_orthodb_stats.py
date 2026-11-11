import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
import orthodb_stats as stats


def payload(group='6005769at2759'):
    return {'status':'ok','data':{'id':group,'public_id':group,'name':'treacle protein','evolutionary_rate':2.5192,'phyletic_profile':{'gene_count':11,'present_in':11,'species_count':5768,'single_copy':11,'multi_copy':0},'gene_architecture':{'protein_median_length':712,'protein_stdev_length':45.6,'exon_median_counts':8,'exon_stdev_counts':0}}}


class StatsTests(unittest.TestCase):
    def test_v13_fields_preserve_zero_and_missing_without_calculating_values(self):
        result=stats.parse('6005769at2759','v13',payload());self.assertEqual(result['evolutionaryRate'],2.5192);self.assertEqual(result['medianProteinLength'],712);self.assertEqual(result['proteinLengthSD'],45.6);self.assertEqual(result['medianExonCount'],8);self.assertEqual(result['multiCopySpecies'],0);self.assertEqual(result['exonCountSD'],0)
        partial=stats.parse('6005769at2759','v13',{'status':'ok','data':{'id':'6005769at2759','evolutionary_rate':'NA'}});self.assertIsNone(partial['evolutionaryRate']);self.assertIsNone(partial['medianProteinLength'])
        wrong=payload();wrong['data']['public_id']='999at2759'
        with self.assertRaisesRegex(ValueError,'different group'):stats.parse('6005769at2759','v13',wrong)

    def test_cache_is_release_specific_and_failed_groups_do_not_discard_successes(self):
        with tempfile.TemporaryDirectory() as root,patch.object(stats,'CACHE',Path(root)),patch.object(stats.subprocess,'run') as run:
            run.return_value.stdout=json.dumps(payload()).encode()
            a=stats.fetch('6005769at2759','v13');b=stats.fetch('6005769at2759','v13');self.assertEqual(a,b);self.assertEqual(run.call_count,1)
            stats.fetch('6005769at2759','v11');self.assertEqual(run.call_count,2)
        def fetch(group,release):
            if group=='2at2759':raise ValueError('unavailable')
            return {'id':group,'release':release}
        with tempfile.TemporaryDirectory() as root,patch.object(stats,'CACHE',Path(root)),patch.object(stats,'fetch',side_effect=fetch):
            result=stats.metadata({'release':'v13','groups':['1at2759','2at2759']});self.assertIn('1at2759',result['groups']);self.assertIn('2at2759',result['errors'])
        with self.assertRaises(ValueError):stats.metadata({'release':'v13','groups':['1;invalid']})


if __name__=='__main__':unittest.main()
