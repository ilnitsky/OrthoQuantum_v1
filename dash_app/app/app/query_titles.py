"""Readable automatic names without replacing names explicitly chosen by users."""
import re

TITLE_FIELDS = ('title', 'query_number', 'auto_title', 'title_custom', 'input_proteins_parsed', 'input_proteins')
DEFAULT_TITLE = re.compile(r'^Query #(\d+)$')


def automatic_title(state, inputs=None):
    title = state.get('title') or ''
    match = DEFAULT_TITLE.fullmatch(title)
    if state.get('title_custom') == '1':
        return {}
    if not match and title != state.get('auto_title'):
        return {}
    number = state.get('query_number') or (match.group(1) if match else '')
    if not str(number).isdigit():
        return {}
    if inputs is None:
        inputs = (state.get('input_proteins_parsed') or state.get('input_proteins') or '').splitlines()
    inputs = [value.strip() for value in inputs if value.strip() and not value.lstrip().startswith('#')]
    if not inputs:
        return {}
    label = ' '.join(inputs[0].split()).replace("'", '’')
    if len(label) > 36:
        label = label[:35] + '…'
    if len(inputs) > 1:
        label += f' +{len(inputs) - 1}'
    generated = f"'{label}' #{number}"
    values = {'title': generated, 'auto_title': generated, 'query_number': str(number)}
    return values if any(state.get(key) != value for key, value in values.items()) else {}
