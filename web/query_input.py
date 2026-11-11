"""Explicit query namespaces; strict symbols never fall back to description search."""
import re

MODES = {'auto', 'identifiers', 'symbols', 'uniprot', 'go', 'kegg', 'interpro', 'orthodb', 'text'}
PATTERNS = {'symbols': r'[A-Za-z][A-Za-z0-9_.-]*', 'uniprot': r'[A-Z0-9]+(?:-\d+)?',
            'go': r'GO:\d{7}', 'kegg': r'(?:K\d{5}|ko\d{5})',
            'interpro': r'IPR\d{6}', 'orthodb': r'\d+at\d+'}

def parse_inputs(raw, mode='auto'):
    if mode not in MODES:
        raise ValueError('Unknown query type.')
    lines = [line.strip() for line in str(raw).splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if mode == 'symbols':
        # Gene tables pasted from spreadsheets: the first column is the symbol.
        lines = [re.split(r'\s+', line)[0] for line in lines]
    if mode in ('go', 'interpro'):
        lines = [line.upper() for line in lines]
    if mode == 'kegg':
        lines = [('ko'+line[2:] if line[:2].lower() == 'ko' else line.upper()) for line in lines]
    values = list(dict.fromkeys(lines))
    if not values or len(values) > 1000 or any(len(v) > 500 for v in values):
        raise ValueError('Enter 1–1,000 queries, one per line (maximum 500 characters each).')
    pattern = PATTERNS.get(mode)
    if pattern:
        invalid = [v for v in values if not re.fullmatch(pattern, v)]
        if invalid:
            raise ValueError('Invalid '+mode+' identifier: '+', '.join(invalid[:5]))
    return values
