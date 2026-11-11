import unittest
from fetch_v13_metadata import parse_rows,query_text
class BulkMetadataTests(unittest.TestCase):
    def test_pages_are_validated_and_zero_missing_preserved(self):
        rows=[{'og':{'value':'http://purl.orthodb.org/odbgroup/100at2759'},'rate':{'value':'0'},'median_length':{'value':'712'}}]
        result=parse_rows(rows,2759)
        self.assertEqual(result,[('100at2759',2759,0,712,None,None,None)])
        for level,cursor in [(33208,''),(2759,'100at2759')]:
            with self.assertRaises(ValueError):parse_rows(rows,level,cursor)
        rows[0]['rate']['value']='nan'
        with self.assertRaises(ValueError):parse_rows(rows,2759)
    def test_bulk_query_is_level_pinned_and_keyset_paginated(self):
        q=query_text(2759,'100at2759',5000)
        self.assertIn('taxonomy/2759',q);self.assertIn('FILTER(STR(?og) >',q);self.assertIn('LIMIT 5000',q)
        with self.assertRaises(ValueError):query_text('bad')
        with self.assertRaises(ValueError):query_text(2759,'bad')
if __name__=='__main__':unittest.main()
