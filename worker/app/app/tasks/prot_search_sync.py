from ..async_executor import async_pool
from ..redis import TAXID_TO_NAME
import mygene

mg = mygene.MyGeneInfo()

def try_int(val):
    try:
        return int(val)
    except Exception:
        return None

@async_pool.in_thread(max_running=6)
def search_for_prot(taxid, prot_codes:str):
    prot_codes = list(
        filter(None, map(str.strip, prot_codes.split('\n')))
    )

    out = mg.querymany(prot_codes, scopes='symbol,reporter,accession', fields='uniprot', species=str(taxid), returnall=True)
    result = []
    name = TAXID_TO_NAME.get(try_int(taxid)) or f"taxid:{taxid}"

    for res in out['out']:
        # uniprot AC:
        if res.get('notfound'):
            result.append(f"# {res['query']} - {name}: not found")
            continue
        try:
            up = res['uniprot']
        except LookupError:
            print("*** LookupError")
            print(res)
            result.append(f"# {res['query']} - {name}: not found")
            continue
        ac = None
        if 'Swiss-Prot' in up:
            if isinstance(up['Swiss-Prot'], str):
                ac = up['Swiss-Prot']
            else:
                try:
                    ac = up['Swiss-Prot'][0]
                except IndexError:
                    pass

        if not ac and 'TrEMBL' in up:
            for ac in up['TrEMBL']:
                if len(ac) == 6: # found a good one
                    break
            # ether 6 char or the last from the list

        if not ac:
            result.append(f"# {res['query']} - {name}: not found")
            print(f"Error with parsing search: {res}")
            continue
        result.append(f"# {res['query']} - {name}:\n{ac}\n")


    return '\n'.join(result)


