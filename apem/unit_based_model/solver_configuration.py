"""
Solver configuration shared by the unit-based allocation and pricing layers.
"""


class SolverConfiguration:
    """
    Collects the optimizer parameters applied to unit-based solves.

    The same object is passed to allocation, redispatch, and pricing routines so
    they use consistent solver settings across a run.
    """

    def __init__(self, MIP_gap, optimality_tol, time_limit, work_limit, threads, presparsify,
                 strict_supply_demand_eq, relaxation, output_flag, verbosity, slack_penalty=1e15):
        """
        Initialize solver settings used for Gurobi-backed unit-based runs.

        :param MIP_gap: relative MIP gap target for mixed-integer solves
        :param optimality_tol: optimality tolerance passed to Gurobi
        :param time_limit: wall-clock time limit in seconds
        :param work_limit: Gurobi work limit
        :param threads: number of solver threads; ``0`` lets Gurobi decide
        :param presparsify: value for the Gurobi ``Presparsify`` parameter
        :param strict_supply_demand_eq: whether supply-demand balance should be enforced strictly
        :param relaxation: whether the optimization model should be solved as a relaxation
        :param output_flag: Gurobi output flag controlling solver log output
        :param verbosity: whether APEM should print progress information around solves
        :param slack_penalty: penalty coefficient used where slack variables are introduced
        """
        self.MIP_gap = MIP_gap
        self.optimality_tol = optimality_tol
        self.time_limit = time_limit
        self.work_limit = work_limit
        self.threads = threads
        self.presparsify = presparsify
        self.strict_supply_demand_eq = strict_supply_demand_eq
        self.relaxation = relaxation
        self.output_flag = output_flag
        self.verbosity = verbosity
        self.slack_penalty = slack_penalty

    def apply_to_model(self, model):
        """
        Apply the stored settings to a Gurobi model instance.

        :param model: Gurobi model to configure before optimization
        """
        model.setParam('MIPGap', self.MIP_gap)
        model.setParam('OptimalityTol', self.optimality_tol)
        model.setParam('TimeLimit', self.time_limit)
        model.setParam('WorkLimit', self.work_limit)
        model.setParam('Threads', self.threads)
        model.setParam('Presparsify', self.presparsify)
        model.setParam('OutputFlag', self.output_flag)
        model.setParam('LogToConsole', self.output_flag)
