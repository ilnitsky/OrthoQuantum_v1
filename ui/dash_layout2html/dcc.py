from mocks import Base

class Store(Base):
    NAME = __qualname__.split('.')[-1]
    COMMENT = True

class Dropdown(Base):
    NAME = __qualname__.split('.')[-1]

class Textarea(Base):
    NAME = "Input"
    PROPS = {"type": "textarea"}

class Slider(Base):
    NAME = "Input"
    PROPS = {"type": "range"}

class Location(Base):
    NAME = __qualname__.split('.')[-1]
    COMMENT = True

class Interval(Base):
    NAME = __qualname__.split('.')[-1]
    COMMENT = True