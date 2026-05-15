from dataclasses import dataclass
import multiprocessing
import os
import sys
import pickle
import random
import time
import argparse
from simulation_model_protocol import SimulationParameters
from fitness_functions import AliveCellsFitness, CircularFitness, SpatialFitnessType, SquaredFitness
from initial_positions import InitialPosition
from physiboss import ModelParameters, Protocols, RemotePhysiboss, LocalPhysiboss
import subprocess
import numpy as np
import time
### Produce a pool of << Subject of analysis; Context>, Fitness>
MAX_REMOTE_JOBS_STOPS_AT = 160*3
MAX_REMOTE_JOBS_RESUME_AT = 70*3

# Sampling Subject - Model + Initial Positions to be tested
@dataclass
class Subjects:
    initial_positions: InitialPosition
    model: ModelParameters
    def get_random_vector(multiplicator, pool_path):
        subjects = []
        families = os.listdir(pool_path)
        families = [x for x in families if os.path.isdir(f"{pool_path}/{x}")]
        for boolean_family in families:
            all_choices = os.listdir(f"{pool_path}/{boolean_family}")
            all_choices = [x for x in all_choices if x.endswith(".bnd")]
            for boolean_model in all_choices:
                boolean_model = boolean_model.replace(".bnd", "")
                model = ModelParameters(
                    boolean_family=boolean_family,
                    boolean_model=boolean_model,
                )
                for N in range(multiplicator):
                    initial_positions_type = InitialPosition.get_random()
                    subject = Subjects(
                        initial_positions=initial_positions_type,
                        model=model
                    )
                    subjects.append(subject)
        return subjects

    def get_random():
        initial_positions_type = InitialPosition.get_random()
        boolean_family = random.choice([
            "EGFTNF", "drosophila","prostate_cancer", "tnf_cell_fate", "cell_cycle", "gastric_cancer", "macrophage"
        ])
        all_choices = os.listdir(f"../protocols/v1/pool/{boolean_family}")
        all_choices = [x for x in all_choices if x.endswith(".bnd")]
        boolean_model = random.choice(all_choices).replace(".bnd", "")
        model = ModelParameters(
            boolean_family=boolean_family,
            boolean_model=boolean_model,
        )
        return Subjects(
            initial_positions=initial_positions_type,
            model=model
        )
    
    @staticmethod
    def fromCSV(parts):
        parts = parts[1:]
        initial_positions = InitialPosition(
            type=parts[0],
            center=(float(parts[1]), float(parts[2])),
            density=float(parts[3]),
            cell_type=parts[4],
            mode=parts[5],
            length=float(parts[6])
        )
        model = ModelParameters(
            boolean_family=parts[7],
            boolean_model=parts[8]
        )
        return Subjects(
            initial_positions=initial_positions,
            model=model
        )

    def toCSV(self):
        x = [
            self.initial_positions.type,
            self.initial_positions.center[0],
            self.initial_positions.center[1],
            self.initial_positions.density,
            self.initial_positions.cell_type,
            self.initial_positions.mode,
            self.initial_positions.length,
            self.model.boolean_family,
            self.model.boolean_model,
        ]
        return ",".join(map(str, x))
        

# Sampling Context - Protocol to be tested with the Subject
@dataclass
class Context:
    #protocol.initial position is ignored and replaced by the one in the Subject 
    protocol: Protocols
    
    def get_random_vector(N):
        X = int(N**(1/6))
        xmin_values = np.linspace(2, 8, X)
        xmax_values = np.linspace(2, 8, X)
        ymin_values = np.linspace(2, 8, X)
        ymax_values = np.linspace(2, 8, X)
        treatment_duration_values = np.linspace(0.2, 0.8, X)
        treatment_period_values = np.linspace(0.1, .4, X)
        contexts = []
        for xmin in xmin_values:
            for xmax in xmax_values:
                for ymin in ymin_values:
                    for ymax in ymax_values:
                        for treatment_duration in treatment_duration_values:
                            for treatment_period in treatment_period_values:
                                contexts.append(Context(
                                    protocol=Protocols(
                                        treatment_duration=treatment_duration,
                                        treatment_period=treatment_period,
                                        xmin=xmin,
                                        xmax=xmax,
                                        ymin=ymin,
                                        ymax=ymax,
                                        initial_positions=None
                                    )
                                ))
        #If due to rounding the number of contexts is less than N, fill with random contexts
        while len(contexts) < N:
            contexts.append(Context.get_random())
        contexts = random.sample(contexts, N)
        return contexts

    def get_random():
        xmin = random.random()*10
        xmax = random.random()*10
        ymin = random.random()*10
        ymax = random.random()*10
        # Create a random protocol
        return Context(
            protocol=Protocols(
                treatment_duration=random.random(),
                treatment_period=random.random()/2,
                xmin=xmin,
                xmax=xmax,
                ymin=ymin,
                ymax=ymax,
                initial_positions=None
            )
        )



class RemotePhysibossInterface:

    def __init__(self, 
                boolean_model_pool: str, 
                remote_hpc_results_path: str,
                remote_hpc_failed_path: str,
                hpc_temp_path: str,
                hpc_login: str,
                hpc_script_name: str
                ):
        self.lock = multiprocessing.Lock()
        self.physiboss = RemotePhysiboss(
            boolean_model_pool,
            remote_hpc_results_path,
            remote_hpc_failed_path,
            hpc_temp_path,
            hpc_login,
            hpc_script_name,
        )

    def run_job(self, model: ModelParameters, protocol: Protocols, job_name: str, sim_params: SimulationParameters):
        self.physiboss.run_remote_and_not_fetch(
            model, protocol, job_name, sim_params, self.lock
        )

    def get_job_list(self):
        return self.physiboss.get_remote_job_list()
    
    def retrieve_job_results(self, destination_folder: str):
        self.physiboss.retrieve_all_remote_jobs(destination_folder)

class LocalPhysibossInterface:
    def __init__(self, pool_path, results_path):
        self.pool_path = pool_path
        self.results_path = results_path

    def run_job(self, model: ModelParameters, protocol: Protocols, job_name: str, sim_params: SimulationParameters):
        out = LocalPhysiboss.run_local(
            model, protocol, sim_params, self.pool_path
        )
        os.system(f"mkdir -p {self.results_path}/{job_name}")
        os.system(f"mv {out} {self.results_path}/{job_name}")


    def get_job_list(self):
        return os.listdir(self.results_path)
    
    def retrieve_job_results(self, destination_folder: str):
        pass

def run_sampling(N_CONTEXT, N_SUBJECT, work_path, pool_path, physiboss, max_jobs_stop=None, max_jobs_resume=None):
    """
    Run the sampling process.
    """
    # Setup output directories
    output_dir = work_path
    result_dir = os.path.join(work_path, "results")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
    
    # Define fitness functions
    fitnesses = [
        AliveCellsFitness(),
        CircularFitness(center=(0, 0), radius=100, fitness_type=SpatialFitnessType.LINEAR),
        CircularFitness(center=(0, 0), radius=100, fitness_type=SpatialFitnessType.LINEAR_WT_DISTRIBUTION),
        SquaredFitness(center=(0, 0), side_length=100, fitness_type=SpatialFitnessType.LINEAR),
        SquaredFitness(center=(0, 0), side_length=100, fitness_type=SpatialFitnessType.LINEAR_WT_DISTRIBUTION),
        CircularFitness(center=(-50, -50), radius=100, fitness_type=SpatialFitnessType.LINEAR),
        CircularFitness(center=(-50, -50), radius=100, fitness_type=SpatialFitnessType.LINEAR_WT_DISTRIBUTION),
        SquaredFitness(center=(-50, -50), side_length=100, fitness_type=SpatialFitnessType.LINEAR),
        SquaredFitness(center=(-50, -50), side_length=100, fitness_type=SpatialFitnessType.LINEAR_WT_DISTRIBUTION),
    ]
    fitnesses_names = [
        "AliveCellsFitness",
        "CircularFitness",
        "CircularFitness_WT_DISTRIBUTION",
        "SquaredFitness",
        "SquaredFitness_WT_DISTRIBUTION",
        "CircularFitness_2",
        "CircularFitness_2_WT_DISTRIBUTION",
        "SquaredFitness_2",
        "SquaredFitness_2_WT_DISTRIBUTION"
    ]

    # Load or generate subjects and contexts
    if (os.path.exists(f"{output_dir}/subjects.csv") and os.path.exists(f"{output_dir}/contexts.pickle")):
        with open(f"{output_dir}/contexts.pickle", "rb") as f:
            contexts = pickle.load(f)
        subjects = []
        with open(f"{output_dir}/subjects.csv", "r") as f:
            for line in f:
                parts = line.strip().split(",")
                subjects.append(Subjects.fromCSV(parts))
        num_sent = len(os.listdir(result_dir))
        results = physiboss.get_job_list()
        num_received = len(results)
        if len(subjects) != N_SUBJECT or len(contexts) != N_CONTEXT:
            exit("The number of subjects or contexts in the existing files does not match the requested number. Please delete the existing files to regenerate them.")
        print(f"Restoring sampling procedure. Sent {num_sent} jobs, received {num_received} results.")

    else:
        subjects = Subjects.get_random_vector(N_SUBJECT, pool_path)
        contexts = Context.get_random_vector(N_CONTEXT)
        # Save the subject
        with open(f"{output_dir}/subjects.csv", "w") as f:
            for i, subject in enumerate(subjects):
                f.write(f"{i},{subject.toCSV()}\n")
        # Save the context
        with open(f"{output_dir}/contexts.pickle", "wb") as f:
            pickle.dump(contexts, f)
        num_sent = 0
        results = []
        num_received = 0


    simulationParameters = SimulationParameters.get_defaults()

    #Compute the raw simulation putouts
    for i, subject in enumerate(subjects):
        with open(f"{output_dir}/{i}_fitness.csv", "a") as f:
            f.write(",".join(fitnesses_names) + "\n")
        for context_index, context in enumerate(contexts):
            # Test the model and protocol
            context.protocol.initial_positions = subject.initial_positions
            try:
                job_name = f"subject_{i}_context_{contexts.index(context)}"
                if (job_name in results):
                    print(f"Skipping job {job_name} as result already exists.")
                    continue

                physiboss.run_job(model=subject.model, protocol=context.protocol, job_name=job_name, sim_params=simulationParameters)
                num_sent += 1

                if max_jobs_stop and max_jobs_resume:
                    if (num_sent - num_received) >= max_jobs_stop:
                        while (num_sent - num_received) >= max_jobs_resume:
                            print(f"Sent {num_sent} jobs, received {num_received} results. Waiting for results...")
                            results = physiboss.get_job_list()
                            num_received = len(results)
                            time.sleep(30)
            except KeyboardInterrupt:
                print("Process interrupted by user. Exiting...")
                return
            except Exception as e:
                print(f"Error: {e} - Skipping subject {i}, context {context_index}.")


    while (num_sent != num_received):
        print("Waiting for all jobs to complete...")
        print(f"Sent {num_sent} jobs, received {num_received} results. Waiting for results...")
        time.sleep(30)
        results = physiboss.get_job_list()
        num_received = len(results)
    
    #Compute the fitness
    print("Computing fitness scores...")
    physiboss.retrieve_job_results(destination_folder=result_dir)
    MAX_STEP = 10

    for step in range(0, MAX_STEP + 1):
        for i, subject in enumerate(subjects):
            with open(f"{output_dir}/{i}_fitness_step_{step}.csv", "w") as f:
                f.write(",".join(fitnesses_names) + "\n")
            for context_index, context in enumerate(contexts):
                file_index = step
                if (file_index < MAX_STEP):
                    while (not os.path.isfile(f"{result_dir}/subject_{i}_context_{context_index}/output/output0000000{file_index}_cells.mat")) and file_index >= 0:
                        file_index -= 1
                    if file_index < 0:
                        print(f"Skipping subject {i}, context {context_index} as no valid step found.")
                        continue
                    job_name = f"subject_{i}_context_{context_index}/output/output0000000{file_index}_cells.mat"
                else:
                    while (not os.path.isfile(f"{result_dir}/subject_{i}_context_{context_index}/output/final_cells.mat")) and file_index > 0:
                        file_index -= 1
                    job_name = f"subject_{i}_context_{context_index}/output/final_cells.mat"
                path = f"{result_dir}/{job_name}"
                if not os.path.exists(path):
                    print(f"Path {path} does not exist. Skipping...")
                    fitness_scores = [np.nan] * len(fitnesses)
                else:
                    fitness_scores = []
                    try:
                        for fitness in fitnesses:
                            fitness_scores.append(fitness.fitness(path))
                    except Exception as e:
                        fitness_scores = [np.nan] * len(fitnesses)
                # Save the fitness scores
                with open(f"{output_dir}/{i}_fitness_step_{step}.csv", "a") as f:
                    f.write(",".join(map(str, fitness_scores)) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run sensitivity analysis for PhysiBoSS simulations')
    
    parser.add_argument('N_Context', type=int, help='Number of contexts to sample')
    parser.add_argument('N_Subject', type=int, help='Number of subjects to sample')
    parser.add_argument('pool_path', type=str, help='Path to the pool of boolean models')
    parser.add_argument('work_path', type=str, help='Working directory path for output files')
    parser.add_argument('--use-remote', action='store_true', help='Enable remote execution')
    parser.add_argument('--remote-url', type=str, default=None, 
                        help='Remote URL for job submission (required if --use-remote is set)')
    parser.add_argument('--remote-results-path', type=str, default=None,
                        help='Remote HPC results path (required if --use-remote is set)')
    parser.add_argument('--remote-failed-path', type=str, default=None,
                        help='Remote HPC failed jobs path (required if --use-remote is set)')
    parser.add_argument('--remote-temp-path', type=str, default=None,
                        help='Remote HPC temporary path (required if --use-remote is set)')
    parser.add_argument('--max-jobs-stop', type=int, default=480,
                        help='Maximum number of concurrent remote jobs before stopping (default: 480)')
    parser.add_argument('--max-jobs-resume', type=int, default=210,
                        help='Resume submitting jobs when count drops below this (default: 210)')
    parser.add_argument('--remote-script-name', type=str, default="remote_job.sh",
                        help='Name of the remote script to be used for job submission (default: remote_job.sh)')
    
    args = parser.parse_args()
    
    # Validate that all remote parameters are provided if use_remote is True
    if args.use_remote:
        if not args.remote_url:
            parser.error("--remote-url is required when --use-remote is set")
        if not args.remote_results_path:
            parser.error("--remote-results-path is required when --use-remote is set")
        if not args.remote_failed_path:
            parser.error("--remote-failed-path is required when --use-remote is set")
        if not args.remote_temp_path:
            parser.error("--remote-temp-path is required when --use-remote is set")
        if not args.remote_script_name:
            parser.error("--remote-script-name is required when --use-remote is set")

    #Initialize the physiboss interface
    if args.use_remote:

        physiboss = RemotePhysiboss(
            boolean_model_pool=args.pool_path,
            remote_hpc_results_path=args.remote_results_path,
            remote_hpc_failed_path=args.remote_failed_path,
            hpc_temp_path=args.remote_temp_path,
            hpc_login=args.remote_url,
            hpc_script_name=args.remote_script_name
        )
        physiboss = RemotePhysibossInterface()
        max_jobs_stop = args.max_jobs_stop
        max_jobs_resume = args.max_jobs_resume
    else:
        physiboss = LocalPhysibossInterface(args.pool_path, args.work_path + "/results")
        max_jobs_stop = None
        max_jobs_resume = None
    
    run_sampling(args.N_Context, args.N_Subject, args.work_path, args.pool_path, physiboss, max_jobs_stop, max_jobs_resume)

