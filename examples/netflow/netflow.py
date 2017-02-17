#!/usr/bin/python

# Copyright 2015, 2016 Opalytics, Inc.

# Solve a multi-commodity flow problem as python package.

# Implement core functionality needed to achieve modularity.
# 1. Define the input data schema
# 2. Define the output data schema
# 3. Create a solve function that accepts a data set consistent with the input
#    schema and (if possible) returns a data set consistent with the output schema.
#
# Provides command line interface via ticdat.standard_main
# For example, typing
#   python netflow.py -i csv_data -o solution_csv_data
# will read from a model stored in .csv files in the csv_data directory
# and write the solution to .csv files in the solution_csv_data directory

from ticdat import TicDatFactory, standard_main, Model, Slicer

# ------------------------ define the input schema --------------------------------
input_schema = TicDatFactory (
     commodities = [["Name"],[]],
     nodes  = [["Name"],[]],
     arcs = [["Source", "Destination"],["Capacity"]],
     cost = [["Commodity", "Source", "Destination"], ["Cost"]],
     inflow = [["Commodity", "Node"],["Quantity"]]
)

# add foreign key constraints
input_schema.add_foreign_key("arcs", "nodes", ['Source', 'Name'])
input_schema.add_foreign_key("arcs", "nodes", ['Destination', 'Name'])
input_schema.add_foreign_key("cost", "nodes", ['Source', 'Name'])
input_schema.add_foreign_key("cost", "nodes", ['Destination', 'Name'])
input_schema.add_foreign_key("cost", "commodities", ['Commodity', 'Name'])
input_schema.add_foreign_key("inflow", "commodities", ['Commodity', 'Name'])
input_schema.add_foreign_key("inflow", "nodes", ['Node', 'Name'])

input_schema.set_data_type("arcs", "Capacity",  max=float("inf"),
                           inclusive_max=True)
input_schema.set_data_type("cost", "Cost")
input_schema.set_data_type("inflow", "Quantity", min=-float("inf"),
                          inclusive_min=False)
# ---------------------------------------------------------------------------------

# ------------------------ define the output schema -------------------------------
solution_schema = TicDatFactory(
        flow = [["Commodity", "Source", "Destination"], ["Quantity"]],
        parameters = [["Key"],["Value"]])
# ---------------------------------------------------------------------------------

# ------------------------ solving section-----------------------------------------
_model_type = "gurobi" # could also be 'cplex' or 'xpress'
def solve(dat):
    """
    core solving routine
    :param dat: a good ticdat for the input_schema
    :return: a good ticdat for the solution_schema, or None
    """

    mdl = Model(_model_type, "netflow")

    flow = {(h, i, j) : mdl.add_var(name='flow_%s_%s_%s' % (h, i, j))
            for h, i, j in dat.cost if (i,j) in dat.arcs}

    flowslice = Slicer(flow)

    # Arc Capacity constraints
    for i_,j_ in dat.arcs:
        mdl.add_constraint(mdl.sum(flow[h,i,j] for h,i,j in flowslice.slice('*',i_, j_))
                     <= dat.arcs[i_,j_]["Capacity"],
                     name='cap_%s_%s' % (i_, j_))


    # Flow conservation constraints. Constraints are generated only for relevant pairs.
    # So we generate a conservation of flow constraint if there is negative or positive inflow
    # quantity, or at least one inbound flow variable, or at least one outbound flow variable.
    for h_,j_ in set(k for k,v in dat.inflow.items() if abs(v["Quantity"]) > 0).union(
            {(h,i) for h,i,j in flow}, {(h,j) for h,i,j in flow}) :
        mdl.add_constraint(
          mdl.sum(flow[h,i,j] for h,i,j in flowslice.slice(h_,'*',j_)) +
              dat.inflow.get((h_,j_), {"Quantity":0})["Quantity"] ==
          mdl.sum(flow[h,i,j] for h,i,j in flowslice.slice(h_, j_, '*')),
                   name='node_%s_%s' % (h_, j_))

    mdl.set_objective(mdl.sum(flow * dat.cost[h, i, j]["Cost"]
                              for (h, i, j),flow in flow.items()))

    # Compute optimal solution
    if mdl.optimize():
        rtn = solution_schema.TicDat()
        for (h, i, j),var in flow.items():
            if mdl.get_solution_value(var) > 0:
                rtn.flow[h,i,j] = mdl.get_solution_value(var)
        rtn.parameters["Total Cost"] = sum(dat.cost[h,i,j]["Cost"] * r["Quantity"]
                                          for (h,i,j),r in rtn.flow.items())
        return rtn
# ---------------------------------------------------------------------------------

# ------------------------ provide stand-alone functionality ----------------------
# when run from the command line, will read/write xls/csv/db/sql/mdb files
if __name__ == "__main__":
    standard_main(input_schema, solution_schema, solve)
# ---------------------------------------------------------------------------------