from euphemia.execution_chain import *
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)
solve_and_analyse_scenario(Datasets.IEEE_RTS)
