class Configuration:
    """
    Includes the values of different parameters that can be set in the optimizer.
    The configuration parameters are applied to both the allocation and pricing problems.
    """
    def __init__(self, MIP_gap, optimality_tol, time_limit, work_limit, threads, presparsify, strict_supply_demand_eq,
                 relaxation, output_flag, verbosity):
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
        
    def apply_to_model(self, model):
        """
        Applies the configuration settings to the given Gurobi model.
        """
        model.setParam('MIPGap', self.MIP_gap)
        model.setParam('OptimalityTol', self.optimality_tol)
        model.setParam('TimeLimit', self.time_limit)
        model.setParam('WorkLimit', self.work_limit)
        model.setParam('Threads', self.threads)
        model.setParam('Presparsify', self.presparsify)
        model.setParam('OutputFlag', self.output_flag)        
