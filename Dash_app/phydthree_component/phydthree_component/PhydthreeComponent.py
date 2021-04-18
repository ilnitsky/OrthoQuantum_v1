# AUTO GENERATED FILE - DO NOT EDIT

from dash.development.base_component import Component, _explicitize_args


class PhydthreeComponent(Component):
    """A PhydthreeComponent component.
ExampleComponent is an example component.
It takes a property, `label`, and
displays it.
It renders an input with the property `value`
which is editable by the user.

Keyword arguments:

- url (string; required):
    A label that will be printed when this component is rendered."""
    @_explicitize_args
    def __init__(self, url=Component.REQUIRED, **kwargs):
        self._prop_names = ['url']
        self._type = 'PhydthreeComponent'
        self._namespace = 'phydthree_component'
        self._valid_wildcard_attributes =            []
        self.available_properties = ['url']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}
        for k in ['url']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')
        super(PhydthreeComponent, self).__init__(**args)
