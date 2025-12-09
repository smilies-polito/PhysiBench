from dataclasses import dataclass
import os
import pickle
import random
import time
from simulation_parameters_optimization import SimulationParameters
from fitness_functions import AliveCellsFitness, CircularFitness, SpatialFitnessType, SquaredFitness
from initial_positions import InitialPosition
from physiboss import ModelParameters, Protocols, Physiboss
import subprocess
import numpy as np
import time
### Produce a pool of << Subject of analysis; Context>, Fitness>

MAX_REMOTE_JOBS_STOPS_AT = 160*3
MAX_REMOTE_JOBS_RESUME_AT = 70*3

@dataclass
class Subjects:
    initial_positions: InitialPosition
    model: ModelParameters
    def get_random_vector(multiplicator):
        subjects = []
        for boolean_family in ["EGFTNF", "drosophila","prostate_cancer", "tnf_cell_fate", "cell_cycle", "gastric_cancer", "macrophage"]:
            all_choices = os.listdir(f"../protocols/v1/pool/{boolean_family}")
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

def run_sampling(N_CONTEXT, N_SUBJECT, fName):
    """
    Run the sampling process.
    """
    output_dir = f"../{fName}"
    result_dir = f"../{fName}/results"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), output_dir))
    print(f"Output directory: {output_dir}")
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

    if (N_CONTEXT is None or N_SUBJECT is None):
        print("Loading existing subjects and contexts...")
        #load the context
        with open(f"{output_dir}/contexts.pickle", "rb") as f:
            contexts = pickle.load(f)
        #load the subjects
        subjects = []
        with open(f"{output_dir}/subjects.csv", "r") as f:
            for line in f:
                parts = line.strip().split(",")
                subjects.append(Subjects.fromCSV(parts))
        num_sent = len(os.listdir(result_dir))
        simulation_start_time = None
        results = Physiboss.get_job_list()
        num_received = len(results)
    else:
        subjects = Subjects.get_random_vector(N_SUBJECT)
        contexts = Context.get_random_vector(N_CONTEXT)
        # Save the subject
        with open(f"{output_dir}/subjects.csv", "w") as f:
            for i, subject in enumerate(subjects):
                f.write(f"{i},{subject.toCSV()}\n")
        # Save the context
        with open(f"{output_dir}/contexts.pickle", "wb") as f:
            pickle.dump(contexts, f)

        num_sent = 0
        simulation_start_time = time.time()

    simulationParameters = SimulationParameters(
        domain_size=206,
        max_time=1700,
        dt_diffusion=0.256,
        dt_mechanics=0.152,
        dt_phenotype=5.718,
        num_threads=3,
        diffusion_coefficient=1070.0,
        speed=3.3,
        intracellular_dt=518
    )

    results = Physiboss.get_job_list()
    num_received = len(results)
    num_sent = num_received

    #Compute the raw simulation putputs
    print("Computing raw simulation outputs...")
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

                Physiboss.run_remote_wt_settings(model=subject.model, protocol=context.protocol, job_name=job_name, sim_params=simulationParameters)
                num_sent += 1

                if (num_sent - num_received) >= MAX_REMOTE_JOBS_STOPS_AT:
                    while (num_sent - num_received) >= MAX_REMOTE_JOBS_RESUME_AT:
                        print(f"Sent {num_sent} jobs, received {num_received} results. Waiting for results...")
                        results = Physiboss.get_job_list()
                        num_received = len(results)
                        time.sleep(30)
            except KeyboardInterrupt:
                print("Process interrupted by user. Exiting...")
                exit()
            except Exception as e:
                print(f"Error: {e}")

    if (simulation_start_time is not None):
        simulation_end_time = time.time()
        delta_time_seconds = simulation_end_time - simulation_start_time
        with open(f"{output_dir}/simulation_time.txt", "w") as f:
            f.write(f"Received {num_received} results out of {num_sent} sent jobs.\n")
            f.write(f"Simulation time: {delta_time_seconds} seconds\n")
            f.write(f"Simulation time: {delta_time_seconds / 60} minutes\n")
            f.write(f"Simulation time: {delta_time_seconds / 3600} hours\n")

    while (num_sent != num_received):
        print("Waiting for all jobs to complete...")
        print(f"Sent {num_sent} jobs, received {num_received} results. Waiting for results...")
        time.sleep(30)
        results = Physiboss.get_job_list()
        num_received = len(results)
    #Compute the fitness
    print("Computing fitness scores...")
    subprocess.run(["rsync", "-avz", '--no-owner',  '--no-group', "rsmeriglio@hpc-lb.polito.it:/home/rsmeriglio/masera/results", f"/boolean/src/{fName}"])   
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
    # Run the sampling process
    print("Loading existing subjects and contexts...")
    #load the context
    with open(f"{output_dir}/contexts.pickle", "rb") as f:
        contexts = pickle.load(f)
    with open("contexts.csv", "w") as f:
        for i, context in enumerate(contexts):
            protocol = context.protocol
            f.write(f"{i},{protocol.treatment_duration},{protocol.treatment_period},{protocol.xmin},{protocol.xmax},{protocol.ymin},{protocol.ymax}\n")

    import sys
    N_Context = int(sys.argv[2]) if len(sys.argv) > 2 else None
    N_Subject = int(sys.argv[3]) if len(sys.argv) > 3 else None
    Name = sys.argv[1] 
    run_sampling(N_Context, N_Subject, Name)
    