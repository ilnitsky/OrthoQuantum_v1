import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('species_options', Path(__file__).parents[1] / 'app/species_options.py')
species = importlib.util.module_from_spec(spec)
spec.loader.exec_module(species)


class SpeciesOptionTests(unittest.TestCase):
    def test_common_species_first_then_alphabetical_without_adding_species(self):
        options = [{'label': 'Zebra mussel', 'value': 1},
                   {'label': 'Mus musculus', 'value': '10090'},
                   {'label': 'Aedes aegypti', 'value': 2},
                   {'label': 'Homo sapiens', 'value': 9606}]
        result = species.preferred_species(options)
        self.assertEqual([x['value'] for x in result], [9606, '10090', 2, 1])
        self.assertEqual(options[0]['value'], 1, 'Do not mutate cached source options')

    def test_other_clades_keep_only_available_species(self):
        options = [{'label': 'Yarrowia lipolytica', 'value': 4952},
                   {'label': 'Saccharomyces cerevisiae', 'value': 4932}]
        result = species.preferred_species(options)
        self.assertEqual([x['value'] for x in result], [4932, 4952])
        self.assertEqual(species.preferred_species([]), [])
