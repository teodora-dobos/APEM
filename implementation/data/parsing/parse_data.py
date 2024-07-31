from abc import ABC, abstractmethod


class ParseData(ABC):
    """Abstract class for parsing.
    """

    @abstractmethod
    def parse_data(self, day):
        pass
