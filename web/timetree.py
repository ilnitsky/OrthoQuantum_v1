"""User-supplied Newick parsing and distance-preserving induced subtrees."""
import math
import re


def parse_newick(text):
    position=0
    def node():
        nonlocal position
        while position<len(text) and text[position].isspace():position+=1
        children=[]
        if position<len(text) and text[position]=='(':
            position+=1
            while True:
                children.append(node())
                if position>=len(text):raise ValueError('Unclosed Newick subtree')
                if text[position]==',':position+=1;continue
                if text[position]==')':position+=1;break
                raise ValueError('Unexpected Newick delimiter')
        start=position;quoted=False;literal_depth=0
        while position<len(text):
            char=text[position]
            if char=="'":
                if quoted and position+1<len(text) and text[position+1]=="'":position+=2;continue
                quoted=not quoted
            if not quoted and char=='(':literal_depth+=1
            elif not quoted and char==')' and literal_depth:literal_depth-=1
            elif not quoted and not literal_depth and char in ',);':break
            position+=1
        token=text[start:position].strip()
        match=re.fullmatch(r'(.*):\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)',token,re.S)
        if not match:raise ValueError('Missing numeric branch length: '+token[:100])
        label=match[1].strip();length=float(match[2])
        if not math.isfinite(length) or length < -0.001:raise ValueError('Invalid branch length')
        correction={'originalLength':length,'lengthCorrection':'tiny negative export edge clamped to zero'} if length<0 else {}
        length=max(0.0,length)
        if label.startswith("'") and label.endswith("'"):label=label[1:-1].replace("''", "'")
        return {'name':label,'length':length,**correction,**({'children':children} if children else {})}
    # The outermost root may omit its incoming edge.
    stripped=text.strip()
    if not re.search(r':[+\-\d.eE]+\s*;?$',stripped):text=stripped.rstrip(';')+':0;'
    root=node()
    if text[position:].strip() not in ('',';'):raise ValueError('Trailing Newick content')
    root['length']=0.0;return root


def leaves(node):return [leaf for child in node['children'] for leaf in leaves(child)] if node.get('children') else [node]


def prune(node, ids, root=True):
    if not node.get('children'):
        if node.get('id') not in ids:return None
        result=dict(node)
        if root:result['length']=0.0
        return result
    children=[child for raw in node['children'] if (child:=prune(raw,ids,False))]
    if not children:return None
    if len(children)==1:
        child=children[0]
        child['length']=None if child.get('length') is None else child['length']+node.get('length',0)
        result=child
    else:result={**node,'children':children}
    if root:result['length']=0.0
    return result


def normalize(name):return ' '.join(name.replace('_',' ').lstrip('*').split()).casefold()
