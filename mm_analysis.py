#!/usr/bin/env python3
import os
import argparse
import sys
from time import sleep
import subprocess
import fileinput
import platform

try:
    OPENAWSEM_LOCATION = os.environ["OPENAWSEM_LOCATION"]
    sys.path.insert(0, OPENAWSEM_LOCATION)
    # print(OPENAWSEM_LOCATION)
except KeyError:
    print("Please set the environment variable name OPENAWSEM_LOCATION.\n Example: export OPENAWSEM_LOCATION='YOUR_OPENAWSEM_LOCATION'")
    exit()

from openmmawsem import *
from helperFunctions.myFunctions import *


parser = argparse.ArgumentParser(
    description="The goal of this python3 code is to automatically create \
    the project template as fast as possible. Written by Wei Lu."
)
parser.add_argument("protein", help="The name of the protein")
parser.add_argument("-d", "--debug", action="store_true", default=False)
parser.add_argument("-c", "--chain", type=str, default="-1")
parser.add_argument("-t", "--thread", type=int, default=2, help="default is using 2 CPUs, -1 is using all")
parser.add_argument("--platform", type=str, default="CPU", help="Could be OpenCL, CUDA and CPU")
parser.add_argument("--trajectory", type=str, default="./movie.pdb")
args = parser.parse_args()

if(args.debug):
    do = print
    cd = print
else:
    do = os.system
    cd = os.chdir

proteinName = pdb_id = args.protein
chain=args.chain.upper()
pdb = f"{pdb_id}.pdb"

simulation_platform = args.platform
platform = Platform.getPlatformByName(simulation_platform)
if simulation_platform == "CPU":
    if args.thread != -1:
        platform.setPropertyDefaultValue("Threads", str(args.thread))
    print(f"{simulation_platform}: {platform.getPropertyDefaultValue('Threads')} threads")


# print(args)
with open('analysis_commandline_args.txt', 'w') as f:
    f.write(' '.join(sys.argv))
    f.write('\n')

if chain == "-1":
    chain = getAllChains("crystal_structure.pdb")
    print("Chains to simulate: ", chain)

# for compute Q
input_pdb_filename = f"{pdb_id}-openmmawsem.pdb"

pdb_trajectory = read_trajectory_pdb_positions(args.trajectory)
oa = OpenMMAWSEMSystem(input_pdb_filename, chains=chain, k_awsem=1.0, xml_filename=OPENAWSEM_LOCATION+"awsem.xml") # k_awsem is an overall scaling factor that will affect the relevant temperature scales

# apply forces
# forceGroupTable_Rev = {11:"Con", 12:"Chain", 13:"Chi", 14:"Excluded", 15:"Rama", 16:"Direct",
#                   17:"Burial", 18:"Mediated", 19:"Fragment"}
forceGroupTable = {"Con":11, "Chain":12, "Chi":13, "Excluded":14, "Rama":15, "Direct":16,
                    "Burial":17, "Mediated":18, "Contact":18, "Fragment":19, "Membrane":20, "ER":21,"TBM_Q":22, "beta_1":23, "beta_2":24,"beta_3":25,"pap":26, "Total":list(range(11, 27)),
                    "Water":[16, 18], "beta":[23, 24, 25], "pap":26, "Q":1}
#forceGroupTable = {"Con":11, "Chain":12, "Chi":13, "Excluded":14, "Rama":15, "Direct":16,
#                    "Burial":17, "Mediated":18, "Contact":18, "Fragment":19, "Membrane":20, "ER":21,"TBM_Q":22, "beta_1":23, "Total":list(range(11, 26)),
#                    "Water":[16, 18], "beta":[23, 24, 25], "Q":1}

forces = [
    oa.q_value("crystal_structure-cleaned.pdb"),
    oa.con_term(),
    oa.chain_term(),
    oa.chi_term(),
    oa.excl_term(),
    oa.rama_term(),
    oa.rama_proline_term(),
    oa.rama_ssweight_term(),
    oa.contact_term(z_dependent=False),
    # oa.apply_beta_term_1(),
    # oa.apply_beta_term_2(),
    # oa.apply_beta_term_3(),
    # oa.pap_term(),
    oa.fragment_memory_term(frag_location_pre="./"),
    # oa.er_term(),
    # oa.tbm_q_term(k_tbm_q=2000),
    # oa.membrane_term(),
]
oa.addForcesWithDefaultForceGroup(forces)

# start simulation
collision_rate = 5.0 / picoseconds

integrator = LangevinIntegrator(300*kelvin, 1/picosecond, 2*femtoseconds)
simulation = Simulation(oa.pdb.topology, oa.system, integrator, platform)

showEnergy = ["Q", "Con", "Chain", "Chi", "Excluded", "Rama", "Contact", "Fragment", "Membrane", "Total"]
#showEnergy = ["Q", "Con", "Chain", "Chi", "Excluded", "Rama", "Contact", "Fragment", "Membrane","ER","TBM_Q","beta_1", "Total"]
# showEnergy = ["Q", "Con", "Chain", "Chi", "Excluded", "Rama", "Contact", "Fragment", "Membrane","ER","TBM_Q","beta_1","beta_2","beta_3","pap", "Total"]
# print("Steps", *showEnergy)
print(" ".join(["{0:<8s}".format(i) for i in ["Steps"] + showEnergy]))
for step, pdb in enumerate(pdb_trajectory):
    simulation.context.setPositions(pdb.positions)
    e = []
    for term in showEnergy:
        if type(forceGroupTable[term]) == list:
            g = set(forceGroupTable[term])
        elif forceGroupTable[term] == -1:
            g = -1
        else:
            g = {forceGroupTable[term]}
        state = simulation.context.getState(getEnergy=True, groups=g)
        if term == "Q":
            termEnergy = state.getPotentialEnergy().value_in_unit(kilojoule_per_mole)
        else:
            termEnergy = state.getPotentialEnergy().value_in_unit(kilocalories_per_mole)
        e.append(termEnergy)
#     print(*e)
    print(" ".join([f"{step:<8}"] + ["{0:<8.2f}".format(i) for i in e]))
#         print(forceGroupTable[term], state.getPotentialEnergy().value_in_unit(kilocalories_per_mole))
