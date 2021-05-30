import asyncio

class VersionChangedException(asyncio.CancelledError):
    pass

class ReportErrorException(Exception):
    pass
