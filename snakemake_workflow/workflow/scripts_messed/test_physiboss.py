
from physiboss import Physiboss
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
from initial_positions import InitialPosition


# Set Physiboss parameters
Physiboss.BOOLEAN_MODEL_POOL = "../protocols/v1/pool" # Must contain families and models subfolders
Physiboss.PHYSIBOSS_PATH = f"../bin/PhysiCell/" # Path to PhysiCell binary folder - must contain config folder
Physiboss.REMOTE_HPC_RESULTS_PATH = "masera/results_test" # Path on the HPC server where results are stored
Physiboss.HPC_TEMP_PATH = "/home/rsmeriglio/masera/jobs" # Temporary path on the HPC server for job submission

# HPC script that will run the job there
hpc_script_name = "masera/run_job_test.sh"

# PhysiBoss settings (should be the same in all simulations)
# get_default already returns the ones used in the analysis
physiboss_settings = SimulationParameters.get_defaults()


# Select a model and protocol
model = ModelParameters(
    boolean_family="cell_cycle",
    boolean_model="V0"
)
protocol = Protocols(
    treatment_duration=0.5, # 0-1
    treatment_period=0.1, # 0-0.5
    xmin=0, # 0-10
    xmax=10, # 0-10
    ymin=0, # 0-10
    ymax=10, # 0-10
    initial_positions=InitialPosition( # See InitialPosition class in initial_positions.py
        type="circle", # "circle" or "square"
        center=(5, 5), # center of the initial positions
        density=0.5, # 0-1
        cell_type=0, # cell type to assign to the initial positions
        mode="sparse", # "sparse", "dense", or "contour"
        length=50 # radius if circle, half side if square
    )
)


# Run a remote simulation
job_name = "hopefully_this_will_work" # Must be unique
Physiboss.run_remote(
    model, protocol, job_name, physiboss_settings, hpc_script_name
    )

print(f"\n Job <{job_name}> submitted to HPC server. Check {Physiboss.REMOTE_HPC_RESULTS_PATH} for results.\n")

# Optional: wait for result
import time
while(True):
    time.sleep(10)
    jobs = Physiboss.get_job_list()
    if job_name in jobs:
        print(f"Job <{job_name}> has completed.")
        break
    else:
        print(f"Job <{job_name}> not yet completed. Checking again in 10 seconds...")