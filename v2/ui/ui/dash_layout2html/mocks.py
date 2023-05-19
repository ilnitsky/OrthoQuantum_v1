def _render_content(content):
    if isinstance(content, str):
        if not content.endswith('\n'):
            content += '\n'
        return content
    elif isinstance(content, Base):
        return str(content)
    elif isinstance(content, list):
        return ''.join(
            _render_content(item) for item in content
        )
    else:
        raise TypeError(repr(content))

def _style(v:dict):
    assert isinstance(v, dict)
    for name, val in v.items():
        yield f"{name}: {val};"

def _render_arg(k, v):
    if k == "style":
        v = ' '.join(_style(v))
    elif k in ("options", "columns"):
        v = repr(v)
        return f'<!-- {k}="{v}" -->'
    else:
        assert isinstance(v, (str, int, float)), f"{k=} {v=}"
    return f'{k}="{v}"'

def _render_args(args: dict):
    for k, v in args.items():
        if v != None:
            yield _render_arg(k, v)

def uniq(iterable):
    seen = set()
    for it in iterable:
        if it in seen:
            continue
        seen.add(it)
        yield it

class Base():
    COMMENT = False
    INFO = ""
    PROPS = {}

    def __init__(self, children=None, className='', **kwargs):
        self.children = children
        self.kwargs = kwargs

        cls = className.split(' ')

        if self.PROPS:
            for k, v in self.PROPS.items():
                if k in self.kwargs:
                    raise Exception(f"PROPS conflict: {self.kwargs}, {self.PROPS}")
                self.kwargs[k] = v
        if j := self.kwargs.pop('justify', None):
            cls.extend(('d-flex', f'justify-content-{j}'))

        if cls:
            res_class = ' '.join(uniq(cls)).strip()
            if res_class:
                self.kwargs['class'] = res_class

        for name in ('options', 'columns'):
            if o := self.kwargs.pop(name, None):
                self.INFO = self.INFO + f"\n{name} = {o}"

    def __str__(self) -> str:
        data = list(_render_args(self.kwargs))
        if data:
            data = f' {" ".join(_render_args(self.kwargs))}'
        else:
            data = ""

        s = ""
        if self.children:
            s += f"<{self.NAME}{data}>\n"
            for line in _render_content(self.children).splitlines(keepends=True):
                s += f"  {line}"
            s += f"</{self.NAME}>\n"
        else:
            s += f"<{self.NAME}{data}/>\n"
        if self.COMMENT:
            s = f'<!--\n{s}-->\n'
        if self.INFO:
            s = f'<!-- {self.INFO} -->\n{s}'
        return s

