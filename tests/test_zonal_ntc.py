import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apem.execution_chain import solve_scenario, Datasets, PowerFlowModels, PricingAlgorithms


class Test_Zonal_NTC_PyPSAEurSmall_PricingAlgorithm(unittest.TestCase):
    """
       Unit tests for evaluating various pricing algorithms on the PyPSAEurSmall dataset under the Zonal NTC power flow model.

       Each test case runs the 'solve_scenario' function with a specific combination of:
       - Datasets.PyPSAEurSmall
       - PowerFlowModels.Zonal_NTC
       - One of the pricing algorithms (IP, ELMP, Join, MinMWP)

       The tests aim to ensure that the 'solve_scenario' function raises no exception.
       """

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

    def test_PyPSAEurSmall_Zonal_NTC_IP(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.Zonal_NTC, PricingAlgorithms.IP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_Zonal_NTC_IP: {e}")

    def test_PyPSAEurSmall_Zonal_NTC_ELMP(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.Zonal_NTC, PricingAlgorithms.ELMP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_Zonal_NTC_ELMP: {e}")

    def test_PyPSAEurSmall_Zonal_NTC_Join(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.Zonal_NTC, PricingAlgorithms.Join)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_Zonal_NTC_Join: {e}")

    def test_PyPSAEurSmall_Zonal_NTC_MinMWP(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.Zonal_NTC, PricingAlgorithms.MinMWP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_Zonal_NTC_MinMWP: {e}")


class Test_Zonal_NTC_PyPSAEurLarge_PricingAlgorithm(unittest.TestCase):
    """
       Unit tests for evaluating various pricing algorithms on the PyPSAEurLarge dataset under the Zonal NTC power flow model.

       Each test case runs the 'solve_scenario' function with a specific combination of:
       - Datasets.PyPSAEurLarge
       - PowerFlowModels.Zonal_NTC
       - One of the pricing algorithms (IP, ELMP, Join, MinMWP)

       The tests aim to ensure that the 'solve_scenario' function raises no exception.
       """

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

    def test_PyPSAEurLarge_Zonal_NTC_IP(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.Zonal_NTC, PricingAlgorithms.IP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_Zonal_NTC_IP: {e}")

    def test_PyPSAEurLarge_Zonal_NTC_ELMP(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.Zonal_NTC, PricingAlgorithms.ELMP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_Zonal_NTC_ELMP: {e}")

    def test_PyPSAEurLarge_Zonal_NTC_Join(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.Zonal_NTC, PricingAlgorithms.Join)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_Zonal_NTC_Join: {e}")

    def test_PyPSAEurLarge_Zonal_NTC_MinMWP(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.Zonal_NTC, PricingAlgorithms.MinMWP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_Zonal_NTC_MinMWP: {e}")


if __name__ == '__main__':
    unittest.main()
