from abc import ABC, abstractmethod
from typing import Optional

from apem.order_book_based_model.euphemia.data.parsing.zonal_scenario import ZonalScenario


class ParseData(ABC):
    """Abstract base class for dataset parsers used by Euphemia.

    Concrete parser implementations load dataset-specific input files and
    return a normalized :class:`ZonalScenario` instance.
    """

    @abstractmethod
    def parse_data(self, day: Optional[object] = None) -> ZonalScenario:
        """Parse raw input data into a :class:`ZonalScenario`.

        :param day: Optional dataset-specific selector used by parsers that can
            load time-filtered inputs. Order-book parsers currently ignore it.
        :return: Parsed scenario ready for model construction.
        """
        raise NotImplementedError
