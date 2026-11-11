"""Deterministic depth-first order of NCBI clades, retaining OrthoDB row IDs."""

class NcbiTaxonomy:
    def __init__(self, snapshot):
        self.snapshot=snapshot;self.nodes=snapshot['nodes'];self.resolved=snapshot['resolved']

    def lineage(self, taxid, fallback=()):
        current=self.resolved.get(str(taxid));status='merged' if current and current!=taxid else 'current'
        if not current:
            status='unresolved'
            current=next((self.resolved[str(i)] for i in reversed(fallback) if str(i) in self.resolved),None)
        if not current:raise ValueError(f'No NCBI lineage or verified ancestor for {taxid}')
        path=[];seen=set();node=current
        while node!=1:
            if node in seen:raise ValueError('NCBI lineage cycle')
            seen.add(node);path.append(node);node=self.nodes[str(node)]['parent']
        return [1]+list(reversed(path)),current,status

    def tree(self, level, members, colors):
        rows=[(leaf,*self.lineage(int(leaf['id']),leaf.get('path',()))) for leaf in members]
        anchor=self.resolved.get(str(level));mismatches=sum(anchor not in path for _,path,_,_ in rows) if anchor else len(rows)
        if mismatches:
            common=list(rows[0][1])
            for _,path,_,_ in rows[1:]:
                length=0
                while length<min(len(common),len(path)) and common[length]==path[length]:length+=1
                common=common[:length]
            anchor=common[-1]
        root={**self.nodes[str(anchor)],'taxid':str(anchor),'color':colors.get(anchor,'#9a7882'),'children':[]};root.pop('parent',None)
        nodes={():root};statuses={'current':0,'merged':0,'unresolved':0}
        for leaf,path,canonical,status in rows:
            statuses[status]+=1;parent=root;prefix=();color=colors.get(anchor,'#9a7882')
            for taxon in path[path.index(anchor)+1:]:
                prefix+=(taxon,);color=colors.get(taxon,color)
                if prefix not in nodes:
                    nodes[prefix]={'taxid':str(taxon),'name':self.nodes[str(taxon)]['name'],'rank':self.nodes[str(taxon)]['rank'],'color':color,'children':[]};parent['children'].append(nodes[prefix])
                parent=nodes[prefix]
            if status=='unresolved':
                prefix+=('unresolved',)
                if prefix not in nodes:nodes[prefix]={'name':'Unresolved NCBI taxonomy','rank':'unresolved','children':[]};parent['children'].append(nodes[prefix])
                parent=nodes[prefix]
            parent['children'].append({k:leaf[k] for k in ('id','name','organismId','assembly','genomeCount')}|
                                     {'color':color,'ncbiTaxid':str(canonical) if status!='unresolved' else None,'ncbiPlacementTaxid':str(canonical),'ncbiScientificName':self.nodes[str(canonical)]['name'] if status!='unresolved' else None,'taxonomyStatus':status})
        def compact(node,is_root=False):
            if not node.get('children'):return node
            # Alphabetize only sibling clades; never sort leaves across clades.
            children=sorted(node['children'],key=lambda c:(c.get('name','').casefold(),c.get('taxid',c.get('id',''))))
            node['children']=[compact(child) for child in children]
            if len(node['children'])==1 and not is_root and node.get('rank')!='unresolved':return node['children'][0]
            return node
        return compact(root,True),{'statuses':statuses,'cohortTaxonomyMismatches':mismatches,'rootTaxid':str(anchor)}
