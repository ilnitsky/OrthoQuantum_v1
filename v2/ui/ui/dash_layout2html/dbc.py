from mocks import Base
class NavItem(Base):
    NAME = __qualname__.split('.')[-1]

class DropdownMenuItem(Base):
    NAME = 'DropdownItem'
    INFO = 'put in DropdownMenu'

class NavLink(Base):
    NAME = __qualname__.split('.')[-1]
    INFO = 'put in NavItem'

class NavbarSimple(Base):
    NAME = 'Nav'

class Row(Base): NAME = __qualname__.split('.')[-1]
class Col(Base): NAME = __qualname__.split('.')[-1]
class InputGroup(Base): NAME = __qualname__.split('.')[-1]
class Checkbox(Base): NAME = __qualname__.split('.')[-1]
class Label(Base): NAME = __qualname__.split('.')[-1]
class Button(Base): NAME = __qualname__.split('.')[-1]
class Tooltip(Base): NAME = __qualname__.split('.')[-1]
class Progress(Base): NAME = __qualname__.split('.')[-1]
class InputGroupAddon(Base):
    NAME = __qualname__.split('.')[-1]
    INFO = "???"

class Input(Base): NAME = __qualname__.split('.')[-1]
class Collapse(Base): NAME = __qualname__.split('.')[-1]
class Card(Base): NAME = __qualname__.split('.')[-1]
class CardBody(Base): NAME = __qualname__.split('.')[-1]
class FormGroup(Base): NAME = __qualname__.split('.')[-1]
class Alert(Base): NAME = __qualname__.split('.')[-1]
class Modal(Base): NAME = __qualname__.split('.')[-1]
class ModalHeader(Base): NAME = __qualname__.split('.')[-1]
class ModalBody(Base): NAME = __qualname__.split('.')[-1]
class ModalFooter(Base): NAME = __qualname__.split('.')[-1]
class Container(Base): NAME = __qualname__.split('.')[-1]

