import gurobipy as gp
from gurobipy import GRB
import pandas as pd

from apem.EU_market_model.euphemia.enums.order_types import OrderType
from apem.EU_market_model.euphemia.utils.calculations import calculate_flexible_order_active_period


class PriceSubproblem:
    """
    Formulate and solve the Euphemia price determination subproblem.
    """

    def __init__(self, master_problem):
        self.master_problem = master_problem
        self.M = master_problem.M
        self.solution_dict_df = pd.DataFrame(self.master_problem.current_alloc_solution)
        self.epsilon = master_problem.epsilon
        self.constraint_meta_data = {}
        self.isConstrained = True  # used for price-based cuts
        self.zonal_pricing = bool(self.master_problem.zonal_pricing_enabled)

        self.pricing_model = gp.Model("Price-Subproblem")

        # MCPs have to be in the range of upper and lower bounds for specific bidding zone.
        if self.zonal_pricing:
            self.MCP = self.pricing_model.addVars(
                self.master_problem.zones,
                self.master_problem.periods,
                name="MCP",
                lb=self.master_problem.price_lower_bound,
                ub=self.master_problem.price_upper_bound,
                vtype=GRB.CONTINUOUS,
            )
        else:
            self.MCP = self.pricing_model.addVars(
                self.master_problem.periods,
                name="MCP",
                lb=self.master_problem.price_lower_bound,
                ub=self.master_problem.price_upper_bound,
                vtype=GRB.CONTINUOUS,
            )

    def _order_zone(self, order) -> str:
        if "zone" in order and pd.notna(order["zone"]):
            return self.master_problem.resolve_zone(order["zone"])
        return self.master_problem.default_zone

    def _price_var(self, t: int, zone: str):
        if self.zonal_pricing:
            return self.MCP[zone, t]
        return self.MCP[t]

    def _master_solution_value(self, variable) -> float:
        """
        Return the incumbent value of a master variable from the callback solution.
        """
        raw_value = self.master_problem.current_alloc_solution.get(variable.VarName)
        if raw_value is None:
            try:
                return float(variable.X)
            except Exception:  # noqa: BLE001
                return 0.0
        if isinstance(raw_value, list):
            return float(raw_value[0])
        return float(raw_value)

    def add_atc_price_consistency_constraints(self) -> None:
        """
        Add ATC active-set price coupling constraints based on incumbent flows.

        For each directed arc (i,j,t) with 0 <= f <= cap:
        - f == 0      -> MCP[j,t] <= MCP[i,t]
        - f == cap    -> MCP[j,t] >= MCP[i,t]
        - 0 < f < cap -> MCP[j,t] == MCP[i,t]
        """
        if (
            not self.zonal_pricing
            or not self.master_problem.network_constraints_enabled
            or self.master_problem.network_model != "ATC"
        ):
            return

        tol = max(float(self.epsilon), 1e-6)
        for arc_idx, (from_zone, to_zone, t) in enumerate(self.master_problem.atc_index):
            cap = float(self.master_problem.atc_cap[(from_zone, to_zone, t)])
            if cap <= tol:
                continue

            flow_var = self.master_problem.f_atc[from_zone, to_zone, t]
            flow = self._master_solution_value(flow_var)
            flow = max(0.0, min(cap, flow))

            from_price = self._price_var(t, from_zone)
            to_price = self._price_var(t, to_zone)
            base_name = f"atc_price_{from_zone}_{to_zone}_{t}_{arc_idx}"

            if flow <= tol:
                self.pricing_model.addConstr(to_price <= from_price + tol, name=f"{base_name}_lb")
            elif cap - flow <= tol:
                self.pricing_model.addConstr(to_price >= from_price - tol, name=f"{base_name}_ub")
            else:
                self.pricing_model.addConstr(to_price - from_price <= tol, name=f"{base_name}_eq1")
                self.pricing_model.addConstr(from_price - to_price <= tol, name=f"{base_name}_eq2")

    def add_fbmc_price_consistency_constraints(self) -> None:
        """
        Add FBMC dual-consistent MCP/PTDF coupling based on incumbent net positions.

        The formulation introduces one system price component per period and dual multipliers
        on FBMC constraints:
        - mu_up[c,t] >= 0 for PTDF * NP <= RAM
        - mu_lo[c,t] >= 0 for PTDF * NP >= LB (when LB exists)

        Zonal prices are linked through stationarity:
            MCP[z,t] = lambda[t] - sum_c PTDF[c,t,z] * (mu_up[c,t] - mu_lo[c,t])

        Active-set complementarity is enforced from the incumbent allocation:
        - if upper slack > tol: mu_up[c,t] = 0
        - if lower slack > tol: mu_lo[c,t] = 0
        """
        if (
            not self.zonal_pricing
            or not self.master_problem.network_constraints_enabled
            or self.master_problem.network_model != "FBMC"
            or not self.master_problem.fb_index
        ):
            return

        tol = max(float(self.epsilon), 1e-6)
        periods = list(self.master_problem.periods)
        fb_index = list(self.master_problem.fb_index)
        fb_lb_index = [idx for idx in fb_index if idx in self.master_problem.fb_lb]

        # Dual variables for FBMC constraints and one unconstrained system component per period.
        fb_lambda = self.pricing_model.addVars(
            periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS, name="fbmc_lambda"
        )
        mu_up = self.pricing_model.addVars(fb_index, lb=0.0, vtype=GRB.CONTINUOUS, name="fbmc_mu_up")
        mu_lo = (
            self.pricing_model.addVars(fb_lb_index, lb=0.0, vtype=GRB.CONTINUOUS, name="fbmc_mu_lo")
            if fb_lb_index
            else gp.tupledict()
        )

        # Build active-set complementarity from incumbent net positions.
        for cnec_id, t in fb_index:
            ptdf_np = 0.0
            for zone in self.master_problem.zones:
                coeff = float(self.master_problem.fb_ptdf_map.get((cnec_id, t, zone), 0.0))
                if coeff == 0.0:
                    continue
                np_value = self._master_solution_value(self.master_problem.net_position[zone, t])
                ptdf_np += coeff * np_value

            upper_slack = float(self.master_problem.fb_ram[(cnec_id, t)]) - ptdf_np
            if upper_slack > tol:
                self.pricing_model.addConstr(
                    mu_up[cnec_id, t] == 0.0,
                    name=f"fbmc_mu_up_zero_if_nonbinding_{cnec_id}_{t}",
                )

            if (cnec_id, t) in self.master_problem.fb_lb:
                lower_slack = ptdf_np - float(self.master_problem.fb_lb[(cnec_id, t)])
                if lower_slack > tol:
                    self.pricing_model.addConstr(
                        mu_lo[cnec_id, t] == 0.0,
                        name=f"fbmc_mu_lo_zero_if_nonbinding_{cnec_id}_{t}",
                    )

        # Zonal MCP stationarity under PTDF constraints.
        for t in periods:
            fb_rows_t = [c for (c, tt) in fb_index if tt == t]
            for zone in self.master_problem.zones:
                expr = gp.LinExpr()
                expr += fb_lambda[t]
                for cnec_id in fb_rows_t:
                    coeff = float(self.master_problem.fb_ptdf_map.get((cnec_id, t, zone), 0.0))
                    if coeff == 0.0:
                        continue
                    expr.addTerms(-coeff, mu_up[cnec_id, t])
                    if (cnec_id, t) in mu_lo:
                        expr.addTerms(coeff, mu_lo[cnec_id, t])

                self.pricing_model.addConstr(
                    self._price_var(t, zone) == expr,
                    name=f"fbmc_mcp_stationarity_{zone}_{t}",
                )

    def extract_prices(self) -> dict:
        if self.zonal_pricing:
            return {
                (zone, t): self.MCP[zone, t].X
                for zone in self.master_problem.zones
                for t in self.master_problem.periods
            }
        return {t: self.MCP[t].X for t in self.master_problem.periods}

    def _emit(self, message: str) -> None:
        if hasattr(self.master_problem, "_emit"):
            self.master_problem._emit(message)

    def solve_price_determination_subproblem(self) -> None:
        """
        Core method of the price determination subproblem: formulate objective and constraints, optimize model.
        """
        self._emit("Formulating price determination subproblem...")

        midpoint = (self.master_problem.price_upper_bound - self.master_problem.price_lower_bound) / 2
        if self.zonal_pricing:
            self.pricing_model.setObjective(
                gp.quicksum(
                    (self.MCP[zone, t] - midpoint) ** 2
                    for zone in self.master_problem.zones
                    for t in self.master_problem.periods
                ),
                GRB.MINIMIZE,
            )
        else:
            self.pricing_model.setObjective(
                gp.quicksum((self.MCP[t] - midpoint) ** 2 for t in self.master_problem.periods),
                GRB.MINIMIZE,
            )

        self.add_step_order_constraints()
        self.add_piecewise_linear_order_constraints()
        self.add_atc_price_consistency_constraints()
        self.add_fbmc_price_consistency_constraints()

        # isConstrained is False for price-based cuts.
        if self.isConstrained:
            self.add_block_order_constraints()
            self.add_complex_order_constraints()
            self.add_scalable_complex_order_constraints()

        self.pricing_model.update()
        self._emit(
            f"Price subproblem formulated: vars={self.pricing_model.NumVars}, constrs={self.pricing_model.NumConstrs}"
        )
        self.pricing_model.write(str(self.master_problem.paths["debug"] / "pricing_model.lp"))
        self._emit("Starting price determination optimization...")
        self.pricing_model.optimize()
        self._emit("Price determination optimization finished.")

    def add_step_order_constraints(self) -> None:
        """
        Add constraints in order to avoid the paradoxical acceptance and rejection of step orders.
        """
        for _, order in self.master_problem.step_orders.iterrows():
            self.add_step_order_constraint(order, infix="normal")

    def add_step_order_constraint(self, step_order, infix) -> None:
        """
        Formulate step order constraint.
        """
        acceptance = step_order["acceptance"]
        q = step_order["q"]
        t = step_order["t"]
        p = step_order["p"]
        order_id = step_order["id"]
        zone = self._order_zone(step_order)
        mcp = self._price_var(t, zone)

        if q == 0:
            return

        # INM -> must have been accepted.
        if acceptance >= 1.0 - self.epsilon:
            if q > 0:
                # Sale: INM -> p <= MCP.
                self.pricing_model.addConstr(mcp >= p - self.epsilon, f"sell_{infix}_step_accepted_{order_id}")
            else:
                # Purchase: INM -> p >= MCP.
                self.pricing_model.addConstr(mcp <= p + self.epsilon, f"buy_{infix}_step_accepted_{order_id}")

        # OTM -> must have been rejected.
        elif acceptance <= self.epsilon:
            if q > 0:
                # Sale: OTM -> p >= MCP.
                self.pricing_model.addConstr(mcp <= p + self.epsilon, name=f"sell_step_rejected_{order_id}")
            else:
                # Purchase: OTM -> p <= MCP.
                self.pricing_model.addConstr(mcp >= p - self.epsilon, name=f"buy_step_rejected_{order_id}")

        # ATM -> must be exactly at the money.
        elif self.epsilon < acceptance < 1.0 - self.epsilon:
            self.pricing_model.addConstr(mcp >= p - self.epsilon, name=f"{infix}_step_partially_accepted_lower_{order_id}")
            self.pricing_model.addConstr(mcp <= p + self.epsilon, name=f"{infix}_step_partially_accepted_upper_{order_id}")

    def add_piecewise_linear_order_constraints(self) -> None:
        """
        Add constraints in order to avoid the paradoxical acceptance and rejection of piecewise linear orders.
        """
        for _, order in self.master_problem.piecewise_linear_orders.iterrows():
            order_id = order["id"]
            p0 = order["p0"]
            p1 = order["p1"]
            q = order["q"]
            t = order["t"]
            acceptance = order["acceptance"]
            zone = self._order_zone(order)
            mcp = self._price_var(t, zone)

            if acceptance >= 1.0 - self.epsilon:
                if q > 0:
                    # Sale: INM -> p <= MCP.
                    self.pricing_model.addConstr(mcp >= p1 - self.epsilon, name=f"sell_PLO_accepted_{order_id}")
                else:
                    # Purchase: INM -> p >= MCP.
                    self.pricing_model.addConstr(mcp <= p1 + self.epsilon, name=f"buy_PLO_accepted_{order_id}")
            elif acceptance <= self.epsilon:
                # OTM -> must have been rejected.
                if q > 0:
                    self.pricing_model.addConstr(mcp <= p0 + self.epsilon, name=f"sell_PLO_rejected_{order_id}")
                else:
                    self.pricing_model.addConstr(mcp >= p0 - self.epsilon, name=f"buy_PLO_rejected_{order_id}")
            elif self.epsilon < acceptance < 1.0 - self.epsilon:
                # ATM -> must be exactly at the money.
                self.pricing_model.addConstr((mcp - p0) / (p1 - p0) - self.epsilon <= acceptance,
                                             name=f"PLO_partially_accepted_lower_{order_id}")
                self.pricing_model.addConstr((mcp - p0) / (p1 - p0) + self.epsilon >= acceptance,
                                             name=f"PLO_partially_accepted_upper_{order_id}")

    def add_block_order_constraints(self) -> None:
        """
        Add constraints in order to avoid the paradoxical acceptance of block orders (PABs).
        """
        for _, block_order in self.master_problem.block_orders.iterrows():
            if block_order["acceptance"] <= self.epsilon:
                continue  # only accepted blocks are relevant

            block_id = block_order["id"]
            p = block_order["p"]
            zone = self._order_zone(block_order)
            q_values = [block_order.get(f"q{t}", 0.0) for t in self.master_problem.periods]

            total_quantity = sum(abs(q) for q in q_values)
            if total_quantity == 0:
                continue

            weighted_mcp = gp.quicksum(
                self._price_var(t, zone) * abs(q) / total_quantity
                for t, q in zip(self.master_problem.periods, q_values)
                if q != 0
            )

            # Use MCP in active period for flexible block orders.
            if block_order["block_type"] == "flexible":
                active_period = calculate_flexible_order_active_period(
                    master_problem=self.master_problem,
                    block_id=block_id,
                )
                if active_period is not None:
                    weighted_mcp = self._price_var(active_period, zone)

            is_sale = any(q > 0 for q in q_values)
            is_linked_parent = any(
                other_order["block_type"] == "linked" and block_order["id"] == other_order["code_prm"]
                for _, other_order in self.master_problem.block_orders.iterrows()
            )

            if not is_linked_parent:
                if is_sale:
                    # Sales order: INM if p < avg(MCP).
                    self.pricing_model.addConstr(weighted_mcp >= p, f"sell_block_INM_{block_id}")
                    self.constraint_meta_data[f"sell_block_INM_{block_id}"] = (OrderType.BLOCK, block_id)
                else:
                    # Purchase order: INM if p > avg(MCP).
                    self.pricing_model.addConstr(weighted_mcp <= p, f"buy_block_INM_{block_id}")
                    self.constraint_meta_data[f"buy_block_INM_{block_id}"] = (OrderType.BLOCK, block_id)

                # Linked leaf blocks are not allowed to generate negative surplus.
                if block_order["block_type"] == "linked":
                    self.add_linked_leafs_positive_surplus(child_order=block_order)
            else:
                # Parent supports family surplus.
                self.add_linked_block_order_constraints(parent_order=block_order)

    def add_linked_block_order_constraints(self, parent_order) -> None:
        """
        Add constraint so that linked block families have non-negative surplus.
        """
        parent_id = parent_order["id"]
        parent_zone = self._order_zone(parent_order)
        children_df = self.master_problem.block_orders[
            (self.master_problem.block_orders["code_prm"] == parent_id)
            & (self.master_problem.block_orders["block_type"] == "linked")
        ]

        self.pricing_model.addConstr(
            gp.quicksum(
                parent_order["acceptance"] * parent_order.get(f"q{t}", 0.0) * (self._price_var(t, parent_zone) - parent_order["p"])
                + gp.quicksum(
                    child["acceptance"] * child.get(f"q{t}", 0.0) * (self._price_var(t, self._order_zone(child)) - child["p"])
                    for _, child in children_df.iterrows()
                )
                for t in self.master_problem.periods
            )
            >= 0,
            f"linked_block_positive_family_parent_{parent_id}",
        )
        self.constraint_meta_data[f"linked_block_positive_family_parent_{parent_id}"] = (OrderType.BLOCK, parent_id)

    def add_linked_leafs_positive_surplus(self, child_order) -> None:
        """
        Add constraint so that linked leaf blocks have non-negative surplus.
        """
        parent_id = child_order["code_prm"]
        child_id = child_order["id"]
        child_zone = self._order_zone(child_order)

        self.pricing_model.addConstr(
            gp.quicksum(
                child_order["acceptance"] * (self._price_var(t, child_zone) - child_order["p"]) * child_order.get(f"q{t}", 0.0)
                for t in self.master_problem.periods
            )
            >= 0,
            f"linked_block_positive_leaf_{child_id}",
        )
        self.constraint_meta_data[f"linked_block_positive_leaf_{child_id}"] = (OrderType.BLOCK, parent_id)

    def add_complex_order_constraints(self) -> None:
        """
        Add constraints to prevent the paradoxical acceptance of complex orders.
        """
        for _, order in self.master_problem.complex_orders.iterrows():
            if order["acceptance"] > self.epsilon and order["condition"] != "load gradient":
                self.add_MIC_MP_constraints(order, self.master_problem.complex_step_orders, OrderType.COMPLEX)
            elif order["acceptance"] > self.epsilon and order["condition"] == "load gradient":
                self.add_load_gradient_constraints(order, self.master_problem.complex_step_orders, OrderType.COMPLEX)

    def add_scalable_complex_order_constraints(self) -> None:
        """
        Add constraints to prevent the paradoxical acceptance of scalable complex orders.
        """
        for _, order in self.master_problem.scalable_complex_orders.iterrows():
            if order["acceptance"] > self.epsilon and order["condition"] != "load gradient":
                self.add_MIC_MP_constraints(order, self.master_problem.scalable_step_orders, OrderType.SCALABLE_COMPLEX)
            elif order["acceptance"] > self.epsilon and order["condition"] == "load gradient":
                self.add_load_gradient_constraints(order, self.master_problem.scalable_step_orders, OrderType.SCALABLE_COMPLEX)

    def add_MIC_MP_constraints(self, order, step_order_df, order_type: OrderType) -> None:
        """
        Constraints to make sure MIC/MP condition is met.
        """
        order_id = order["id"]
        parent_column = "complex_order_id" if order_type == order_type.COMPLEX else "scalable_order_id"
        variable_expected_value = 0
        actual_value = gp.LinExpr()

        for _, step_order in step_order_df.iterrows():
            if step_order[parent_column] != order_id:
                continue

            if order_type == order_type.COMPLEX:
                variable_expected_value += step_order["acceptance"] * order["variable_term"] * abs(step_order["q"])
            else:
                variable_expected_value += step_order["acceptance"] * step_order["p"] * abs(step_order["q"])

            step_zone = self._order_zone(step_order)
            actual_value += step_order["acceptance"] * abs(step_order["q"]) * self._price_var(step_order["t"], step_zone)

        expected_value = order["fixed_term"] + variable_expected_value
        label_MP = f"MP_condition_CO_{order_id}" if order_type == order_type.COMPLEX else f"MP_condition_SCO_{order_id}"
        label_MIC = f"MIC_condition_CO_{order_id}" if order_type == order_type.COMPLEX else f"MIC_condition_SCO_{order_id}"

        if order["condition"] == "MP":
            self.pricing_model.addConstr(actual_value <= expected_value, label_MP)
            self.constraint_meta_data[label_MP] = (order_type, order_id)
        elif order["condition"] == "MIC":
            self.pricing_model.addConstr(actual_value >= expected_value, label_MIC)
            self.constraint_meta_data[label_MIC] = (order_type, order_id)

    def add_load_gradient_constraints(self, order, step_order_df, order_type: OrderType) -> None:
        """
        Constraints to make sure load gradient orders have a positive surplus.
        """
        order_id = order["id"]
        surplus_expr = gp.LinExpr()
        parent_column = "complex_order_id" if order_type == order_type.COMPLEX else "scalable_order_id"

        for _, step in step_order_df.iterrows():
            if step[parent_column] != order_id:
                continue
            t = step["t"]
            p = step["p"]
            q = step["q"]
            accept = step["acceptance"]
            step_zone = self._order_zone(step)
            surplus_expr += accept * q * (self._price_var(t, step_zone) - p)

        label = (
            f"load_gradient_surplus_CO_{order_id}"
            if order_type == order_type.COMPLEX
            else f"load_gradient_SCO_{order_id}"
        )
        self.pricing_model.addConstr(surplus_expr >= 0.0, name=label)
        self.constraint_meta_data[label] = (order_type, order_id)
