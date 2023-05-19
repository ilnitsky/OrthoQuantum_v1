from mocks import Base

class DataTable(Base):
    NAME = __qualname__.split('.')[-1]
    INFO = "Convert to regular paginated table"
