import unittest
from query_input import parse_inputs

class QueryInputTests(unittest.TestCase):
    def test_symbol_table_and_normalization(self):
        self.assertEqual(parse_inputs('A1CF\t#\t24086\tdescription\nBRCA2 other\nA1CF','symbols'),['A1CF','BRCA2'])
        self.assertEqual(parse_inputs('go:0005730','go'),['GO:0005730'])
        self.assertEqual(parse_inputs('KO04010\nk00001','kegg'),['ko04010','K00001'])
        self.assertEqual(parse_inputs('long protein description','text'),['long protein description'])
        self.assertEqual(len(parse_inputs('\n'.join('GENE'+str(i) for i in range(500)),'symbols')),500)
    def test_invalid_namespaces(self):
        for mode,value in [('go','BRCA2'),('interpro','GO:0005730'),('orthodb','junk'),('symbols','123'),('unknown','A')]:
            with self.assertRaises(ValueError):parse_inputs(value,mode)
