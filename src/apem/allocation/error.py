class Error:

    def __init__(self, status):
        self._status = status

    @property
    def status(self):
        return self._status
