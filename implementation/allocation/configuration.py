class Configuration:
    """Includes the values of different parameters that can be set in the optimizer.
    """

    def __init__(self, MIP_gap, optimality_tol, time_limit, work_limit, threads, presparsify, strict_supply_demand_eq,
                 relaxation, output_flag):
        self.MIP_gap = MIP_gap
        self.optimality_tol = optimality_tol
        self.time_limit = time_limit
        self.work_limit = work_limit
        self.threads = threads
        self.presparsify = presparsify
        self.strict_supply_demand_eq = strict_supply_demand_eq
        self.relaxation = relaxation
        self.output_flag = output_flag
