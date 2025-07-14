from gurobipy import GRB
import gurobipy as gp

def add_no_good_cut(self, callback_model) -> None:
    # create cut that makes current solution invalid
    terms = []
    # match variable from current solution with gurobi variable from model
    for gurobi_acceptance_var in callback_model.getVars():
        if gurobi_acceptance_var.VType == GRB.BINARY:
            solution_value = self.current_alloc_solution.get(gurobi_acceptance_var.VarName)
            if solution_value is None:
                print(f"{gurobi_acceptance_var.VarName} not found in solution dict")
                continue
            if solution_value[0] > 0.5:
                terms.append(1 - gurobi_acceptance_var)
            else:
                terms.append(gurobi_acceptance_var)
    if terms:
        expr = gp.quicksum(terms)
        callback_model.cbLazy(expr >= 1)
        print(f"Added no good cut: {expr} >= 1")