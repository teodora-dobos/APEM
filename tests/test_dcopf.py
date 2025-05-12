import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apem.execution_chain import solve_scenario, Datasets, PowerFlowModels, PricingAlgorithms


class Test_DCOPF_IEEERTS_PricingAlgorithm(unittest.TestCase):
    """
       Unit tests for evaluating the pricing algorithms on the IEEE RTS dataset under the DCOPF power flow model.

       Each test case runs the 'solve_scenario' function with a specific combination of:
       - Datasets.IEEE_RTS
       - PowerFlowModels.DCOPF
       - One of the pricing algorithms (IP, ELMP, Join, MinMWP)

       The tests aim to ensure that the 'solve_scenario' function raises no exception.
       """

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

    def test_IEEE_RTS_DCOPF_IP(self):
        try:
            solve_scenario(Datasets.IEEE_RTS, PowerFlowModels.DCOPF, PricingAlgorithms.IP)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_IP: {e}")

    def test_IEEE_RTS_DCOPF_ELMP(self):
        try:
            solve_scenario(Datasets.IEEE_RTS, PowerFlowModels.DCOPF, PricingAlgorithms.ELMP)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_ELMP: {e}")

    def test_IEEE_RTS_DCOPF_Join(self):
        try:
            solve_scenario(Datasets.IEEE_RTS, PowerFlowModels.DCOPF, PricingAlgorithms.Join)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_Join: {e}")

    def test_IEEE_RTS_DCOPF_MinMWP(self):
        try:
            solve_scenario(Datasets.IEEE_RTS, PowerFlowModels.DCOPF, PricingAlgorithms.MinMWP)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_MinMWP: {e}")


class Test_DCOPF_ARPA_PricingAlgorithm(unittest.TestCase):
    """
       Unit tests for evaluating various pricing algorithms on the ARPA dataset under the DCOPF power flow model.

       Each test case runs the 'solve_scenario' function with a specific combination of:
       - Datasets.ARPA
       - PowerFlowModels.DCOPF
       - One of the pricing algorithms (IP, ELMP, Join, MinMWP)

       The tests aim to ensure that the 'solve_scenario' function raises no exception.
       """

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

    def test_ARPA_DCOPF_IP(self):
        try:
            solve_scenario(Datasets.ARPA, PowerFlowModels.DCOPF, PricingAlgorithms.IP)
        except Exception as e:
            self.fail(f"Exception raised in test_ARPA_DCOPF_IP: {e}")

    def test_ARPA_DCOPF_ELMP(self):
        try:
            solve_scenario(Datasets.ARPA, PowerFlowModels.DCOPF, PricingAlgorithms.ELMP)
        except Exception as e:
            self.fail(f"Exception raised in test_ARPA_DCOPF_ELMP: {e}")

    def test_ARPA_DCOPF_Join(self):
        try:
            solve_scenario(Datasets.ARPA, PowerFlowModels.DCOPF, PricingAlgorithms.Join)
        except Exception as e:
            self.fail(f"Exception raised in test_ARPA_DCOPF_Join: {e}")

    def test_ARPA_DCOPF_MinMWP(self):
        try:
            solve_scenario(Datasets.ARPA, PowerFlowModels.DCOPF, PricingAlgorithms.MinMWP)
        except Exception as e:
            self.fail(f"Exception raised in test_ARPA_DCOPF_MinMWP: {e}")


class Test_DCOPF_PyPSAEurSmall_PricingAlgorithm(unittest.TestCase):
    """
       Unit tests for evaluating various pricing algorithms on the PyPSAEurSmall dataset under the DCOPF power flow model.

       Each test case runs the 'solve_scenario' function with a specific combination of:
       - Datasets.PyPSAEurSmall
       - PowerFlowModels.DCOPF
       - One of the pricing algorithms (IP, ELMP, Join, MinMWP)

       The tests aim to ensure that the 'solve_scenario' function raises no exception.
       """

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

    def test_PyPSAEurSmall_DCOPF_IP(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.DCOPF, PricingAlgorithms.IP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_DCOPF_IP: {e}")

    def test_PyPSAEurSmall_DCOPF_ELMP(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.DCOPF, PricingAlgorithms.ELMP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_DCOPF_ELMP: {e}")

    def test_PyPSAEurSmall_DCOPF_Join(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.DCOPF, PricingAlgorithms.Join)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_DCOPF_Join: {e}")

    def test_PyPSAEurSmall_DCOPF_MinMWP(self):
        try:
            solve_scenario(Datasets.PyPSAEurSmall, PowerFlowModels.DCOPF, PricingAlgorithms.MinMWP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurSmall_DCOPF_MinMWP: {e}")


class Test_DCOPF_PyPSAEurLarge_PricingAlgorithm(unittest.TestCase):
    """
       Unit tests for evaluating various pricing algorithms on the PyPSAEurLarge dataset under the DCOPF power flow model.

       Each test case runs the 'solve_scenario' function with a specific combination of:
       - Datasets.PyPSAEurLarge
       - PowerFlowModels.DCOPF
       - One of the pricing algorithms (IP, ELMP, Join, MinMWP)

       The tests aim to ensure that the 'solve_scenario' function raises no exception.
       """

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

    def test_PyPSAEurLarge_DCOPF_IP(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.DCOPF, PricingAlgorithms.IP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_DCOPF_IP: {e}")

    def test_PyPSAEurLarge_DCOPF_ELMP(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.DCOPF, PricingAlgorithms.ELMP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_DCOPF_ELMP: {e}")

    def test_PyPSAEurLarge_DCOPF_Join(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.DCOPF, PricingAlgorithms.Join)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_DCOPF_Join: {e}")

    def test_PyPSAEurLarge_DCOPF_MinMWP(self):
        try:
            solve_scenario(Datasets.PyPSAEurLarge, PowerFlowModels.DCOPF, PricingAlgorithms.MinMWP)
        except Exception as e:
            self.fail(f"Exception raised in test_PyPSAEurLarge_DCOPF_MinMWP: {e}")


class Test_DCOPF_PJM_PricingAlgorithm(unittest.TestCase):
    """
       Unit tests for evaluating the pricing algorithms on the PJM dataset under the DCOPF power flow model.

       Each test case runs the 'solve_scenario' function with a specific combination of:
       - Datasets.PJM
       - PowerFlowModels.DCOPF
       - One of the pricing algorithms (IP, ELMP, Join, MinMWP)

       The tests aim to ensure that the 'solve_scenario' function raises no exception.
       """

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(__file__)))

    def test_PJM_DCOPF_IP(self):
        try:
            solve_scenario(Datasets.PJM, PowerFlowModels.DCOPF, PricingAlgorithms.IP)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_IP: {e}")

    def test_PJM_DCOPF_ELMP(self):
        try:
            solve_scenario(Datasets.PJM, PowerFlowModels.DCOPF, PricingAlgorithms.ELMP)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_ELMP: {e}")

    def test_PJM_DCOPF_Join(self):
        try:
            solve_scenario(Datasets.PJM, PowerFlowModels.DCOPF, PricingAlgorithms.Join)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_Join: {e}")

    def test_PJM_DCOPF_MinMWP(self):
        try:
            solve_scenario(Datasets.PJM, PowerFlowModels.DCOPF, PricingAlgorithms.MinMWP)
        except Exception as e:
            self.fail(f"Exception raised in test_IEEE_RTS_DCOPF_MinMWP: {e}")


if __name__ == '__main__':
    unittest.main()
