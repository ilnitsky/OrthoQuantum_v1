"""Export the legacy guide without importing Dash or executing application code."""
import ast
from html import escape
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent


def export():
    source=ast.parse((REPO/'dash_app/app/app/layout/layout.py').read_text())
    function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='about')
    items=next(n.value for n in function.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='items' for t in n.targets))
    headings=[]
    def render(node):
        if isinstance(node,ast.Constant):return escape(str(node.value))
        if isinstance(node,ast.List):return ''.join(render(n) for n in node.elts)
        if not isinstance(node,ast.Call):raise ValueError('Unexpected guide expression')
        if isinstance(node.func,ast.Name) and node.func.id=='sized_img':
            image=ast.literal_eval(node.args[0].args[0])
            if image not in {f'tutorial/{i}.png' for i in range(1,11)}:raise ValueError('Unexpected guide image')
            src='/'+image;number=Path(image).stem
            return f'<figure><a href="{src}" target="_blank" rel="noopener"><img src="{src}" alt="Original OrthoQuantum guide, figure {number}" loading="lazy"></a><figcaption>Figure {number} · Original interface</figcaption></figure>'
        if not isinstance(node.func,ast.Attribute) or not isinstance(node.func.value,ast.Name) or node.func.value.id!='html':raise ValueError('Unexpected guide component')
        name=node.func.attr;tags={'P':'p','I':'em','H3':'h3','H5':'h5','Ul':'ul','Li':'li','A':'a'}
        tag=tags[name];attrs=''
        if name in ('H3','H5'):
            anchor='guide-'+str(len(headings)+1);title=ast.literal_eval(node.args[0]);headings.append((name,title,anchor));attrs=f' id="{anchor}"'
        if name=='A':
            href=next(ast.literal_eval(k.value) for k in node.keywords if k.arg=='href')
            attrs=f' href="{escape(href,quote=True)}" target="_blank" rel="noopener noreferrer"'
        return f'<{tag}{attrs}>'+render(node.args[0])+f'</{tag}>'
    content=''.join(render(n) for n in items.elts)
    toc=''.join(f'<li class="{"subheading" if level=="H5" else ""}"><a href="#{anchor}">{escape(title)}</a></li>' for level,title,anchor in headings)
    template=(ROOT/'public/index.html').read_text();header=template[template.index('<div class="institution">'):template.index('<main>')]
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Help / About · OrthoQuantum</title><link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/style.css"><script type="module" src="/jobs.mjs"></script></head><body>'''+header+'''<main class="about-document"><h1>OrthoQuantum v1.0 · Help / About</h1><p class="guide-note">The original guide is preserved below, including its text and screenshots. Some labels and features describe the earlier interface. BLAST is currently unavailable. PANTHER profiles open through the view switcher; the current correlation clustermap uses binary presence with a blue–white–red scale.</p><nav class="card guide-contents" aria-label="Guide contents"><h2>Contents</h2><ul>'''+toc+'</ul></nav><article class="card">'+content+'</article><a href="/">Back to queries</a></main></body></html>'
    (ROOT/'public/about.html').write_text(page)
    target=ROOT/'public/tutorial';target.mkdir(exist_ok=True)
    for i in range(1,11):shutil.copyfile(REPO/f'dash_app/app/app/assets/tutorial/{i}.png',target/f'{i}.png')


if __name__=='__main__':export()
