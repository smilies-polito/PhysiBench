from dataclasses import dataclass
import os
import pickle
import random
import time
from fitness_functions import AliveCellsFitness, CircularFitness, SpatialFitnessType, SquaredFitness
from initial_positions import InitialPosition
from physiboss import ModelParameters, Protocols, Physiboss
import subprocess
import numpy as np
import time
import re
### Produce a pool of << Subject of analysis; Context>, Fitness>

MAX_REMOTE_JOBS_STOPS_AT = 300
MAX_REMOTE_JOBS_RESUME_AT = 100

@dataclass
class Subjects:
    initial_positions: InitialPosition
    model: ModelParameters
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
        X = 3#int(N**(1/6))
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

@dataclass 
class SimulationParameters:
    domain_size: float  # 200-500
    max_time: float     # 2000-5000
    dt_diffusion: float # 0.1-0.4
    dt_mechanics: float # 0.1-0.4
    dt_phenotype: float # 6
    num_threads: int    # 1-4
    diffusion_coefficient: float # 800-1600
    speed: float        # 1-3
    intracellular_dt: int = 1000 #500 - 1800

    def to_hash(self):
        def to_two_decimals(x):
            return f"{x:.1f}"
        def to_int(x):
            return f"{int(x)}"
        return "_".join([
            to_two_decimals(self.domain_size),
            to_int(self.max_time),
            to_two_decimals(self.dt_diffusion),
            to_two_decimals(self.dt_mechanics),
            to_two_decimals(self.dt_phenotype),
            to_int(self.num_threads),
            to_int(self.diffusion_coefficient),
            to_two_decimals(self.speed)
        ])


EXPERIMENT_MAIN_DIR = "meta_opt"
NUM_CONTEXTS = 45
NUM_SUBJECTS = 17
#NUM_CONTEXTS = 1
#NUM_SUBJECTS = 2

import random

cache = {}

def run_sampling(subjects, contexts, simulationParameters):
    """
    Run the sampling process.
    """
    global cache
    cache_key = simulationParameters.to_hash()
    if cache_key in cache:
        print(f"Cache hit for {cache_key}. Returning cached result.")
        return cache[cache_key]
    
    output_dir = f"../{EXPERIMENT_MAIN_DIR}/sampling"
    result_dir = f"{output_dir}/results"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), output_dir))
    print(f"Output directory: {output_dir}")
    fitnesses = [
        AliveCellsFitness()
    ]
    fitnesses_names = [
        "AliveCellsFitness"
    ]

    num_sent = 0
    delta_time_seconds = 0

    #Compute the raw simulation putputs
    for i, subject in enumerate(subjects):
        with open(f"{output_dir}/{i}_fitness.csv", "a") as f:
            f.write(",".join(fitnesses_names) + "\n")
        for context_index, context in enumerate(contexts):
            # Test the model and protocol
            context.protocol.initial_positions = subject.initial_positions
            try:
                job_name = f"subject_{i}_context_{contexts.index(context)}"
                Physiboss.run_remote_wt_settings(model=subject.model, protocol=context.protocol, job_name=job_name, sim_params=simulationParameters)
                num_sent += 1
                num_received = len(os.listdir(result_dir))

                if (num_sent - num_received) >= MAX_REMOTE_JOBS_STOPS_AT:
                    while (num_sent - num_received) >= MAX_REMOTE_JOBS_RESUME_AT:
                        print(f"Sent {num_sent} jobs, received {num_received} results. Waiting for results...")
                        time.sleep(60)
                        subprocess.run(["rsync", "-avz", '--no-owner',  '--no-group', "rsmeriglio@hpc-lb.polito.it:/home/rsmeriglio/masera/results", f"{output_dir}"])
                        num_received = len(os.listdir(result_dir))
            except KeyboardInterrupt:
                print("Process interrupted by user. Exiting...")
                exit()
            except Exception as e:
                print(f"Error: {e}")

    
    #delta_time_seconds = simulation_end_time - simulation_start_time


    waited = 0
    while (num_sent != num_received):
        print(f"Sent {num_sent} jobs, received {num_received} results. Waiting for results...")
        time.sleep(120)
        subprocess.run(["rsync", "-avz", '--no-owner',  '--no-group', "rsmeriglio@hpc-lb.polito.it:/home/rsmeriglio/masera/results", f"{output_dir}"])
        num_received = len(os.listdir(result_dir))
        waited += 1
        if waited > 2 and num_received + 10 >= num_sent:
            print("Waiting too long for results. Exiting...")
            break
    
    #Compute the fitness
    print("Computing fitness scores...")
    scores_by_subject = []
    for i, subject in enumerate(subjects):
        scores_by_context = []
        for context_index, context in enumerate(contexts):
            job_name = f"subject_{i}_context_{context_index}"
            path = f"{result_dir}/{job_name}/output/final_cells.mat"
            if not os.path.exists(path):
                print(f"Path {path} does not exist. Skipping...")
            else:
                try:
                    for fitness in fitnesses:
                        scores_by_context.append(fitness.fitness(path))
                    with open(f"{result_dir}/{job_name}/output/time.txt", "r") as f:
                        content = f.read()
                        match = re.search(r"Real:\s*([0-9]+(?:\.[0-9]+)?)", content)
                        if match:
                            delta_time_seconds+=float(match.group(1))


                except Exception as e:
                    pass
        scores_by_subject.append(scores_by_context)
    # Fix length of scores_by_subject
    max_len = -1
    for i, subject_scores in enumerate(scores_by_subject):
        max_len = max(max_len, len(subject_scores))
    for i, subject_scores in enumerate(scores_by_subject):
        if len(subject_scores) < max_len:
            avg = sum(subject_scores) / len(subject_scores) if (subject_scores and len(subject_scores)>0) else 0
            subject_scores.extend([avg] * (max_len - len(subject_scores)))
    scores_by_subject = np.array(scores_by_subject)
    for i in range(scores_by_subject.shape[0]):
        scores_by_subject[i,:][np.isnan(scores_by_subject[i,:])] = np.nanmean(scores_by_subject[i,:])
    std_individual = []
    for j in range(scores_by_subject.shape[0]):
        m = np.mean(scores_by_subject[j])
        if m == 0:
            std_individual.append(0)
        else:
            std_individual.append(np.std(scores_by_subject[j])/m)
    
    std = np.median(std_individual)
    os.system(f"rm -rf {output_dir}")
    os.system(f"ssh rsmeriglio@hpc-lb.polito.it 'rm -rf /home/rsmeriglio/masera/results/*'")
    with open(f"../{EXPERIMENT_MAIN_DIR}/simulation.txt", "a") as f:
        f.write(
            f"{simulationParameters.domain_size},"
            f"{simulationParameters.max_time},"
            f"{simulationParameters.dt_diffusion},"
            f"{simulationParameters.dt_mechanics},"
            f"{simulationParameters.dt_phenotype},"
            f"{simulationParameters.num_threads},"
            f"{simulationParameters.diffusion_coefficient},"
            f"{simulationParameters.speed},"
            f"{simulationParameters.intracellular_dt},"
            f"{std},"
            f"{delta_time_seconds}\n"
        )
    cache[cache_key] = (std, delta_time_seconds)
    return std, delta_time_seconds

STD_THRESHOLD = 0.05

def fitness(std, delta_time_seconds):
    global STD_THRESHOLD
    if std < STD_THRESHOLD:
        return 1000000000
    STD_THRESHOLD = min(std, 0.1)
    return delta_time_seconds - (std * 10 * 60)



def run_de(subjects, contexts, bounds):
    from scipy.optimize import differential_evolution
    result = differential_evolution(
        lambda x: fitness(*run_sampling(subjects, contexts, SimulationParameters(*x))),
        bounds,
        popsize=2,
        seed=1,
        strategy='best1exp',
        mutation=(0.7, 1.5),
        recombination=0.8,
        atol=1e-2,
        updating='deferred'
    )

def setup():
    with open(f"../{EXPERIMENT_MAIN_DIR}/simulation.txt", "w") as f:
        f.write(
            "domain_size,"
            "max_time,"
            "dt_diffusion,"
            "dt_mechanics,"
            "dt_phenotype,"
            "num_threads,"
            "diffusion_coefficient,"
            "speed,"
            "intracellular_dt,"
            "std,"
            "delta_time_seconds\n"
        )
    subjects = [Subjects.get_random() for _ in range(NUM_SUBJECTS)]
    contexts = Context.get_random_vector(NUM_CONTEXTS)
    # Save the subject
    with open(f"../{EXPERIMENT_MAIN_DIR}/subjects.csv", "w") as f:
        for i, subject in enumerate(subjects):
            f.write(f"{i},{subject.toCSV()}\n")
    # Save the context
    with open(f"../{EXPERIMENT_MAIN_DIR}/contexts.pickle", "wb") as f:
        pickle.dump(contexts, f)

    bounds = [
        (200, 500),          # domain_size
        (500, 5000),        # max_time
        (0.1, 0.4),          # dt_diffusion
        (0.1, 0.4),          # dt_mechanics
        (5, 6),              # dt_phenotype (fixed value)
        (1, 5),              # num_threads
        (800, 1600),         # diffusion_coefficient
        (1, 4),              # speed
        (350, 1800)          # intracellular_dt
                    # intracellular_dt must be < max_time
    ]
    run_de(subjects, contexts, bounds)

def run_candidates():
    def read_simulation_parameters_from_csv(filepath):
        simulation_params_list = []
        import csv
        with open(filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                params = SimulationParameters(
                    domain_size=float(row['domain_size']),
                    max_time=float(row['max_time']),
                    dt_diffusion=float(row['dt_diffusion']),
                    dt_mechanics=float(row['dt_mechanics']),
                    dt_phenotype=float(row['dt_phenotype']),
                    num_threads=int(float(row['num_threads'])),
                    diffusion_coefficient=float(row['diffusion_coefficient']),
                    speed=float(row['speed']),
                    intracellular_dt=float(row['intracellular_dt'])
                )
                simulation_params_list.append(params)
        return simulation_params_list
    # Read the candidate parameters
    simulation_parameters = read_simulation_parameters_from_csv(f"../{EXPERIMENT_MAIN_DIR}/candidates.txt")
    # Set up experimental contexts and subjects
    subjects = [Subjects.get_random() for _ in range(40)]
    contexts = Context.get_random_vector(80)

    #Debug
    simulation_parameters = [
        SimulationParameters(
                    domain_size=500,
                    max_time=12000,
                    dt_diffusion=0.01,
                    dt_mechanics=0.01,
                    dt_phenotype=6,
                    num_threads=3,
                    diffusion_coefficient=1200,
                    speed=1,
                    intracellular_dt=1440
                )
    ]

    log_file = open(f"../{EXPERIMENT_MAIN_DIR}/simulation_log.txt", "a")

    # Run each candidate
    for candidate in simulation_parameters:
        print("Running candidate:", candidate)
        log_file.write(
            f"\n\n\nRunning candidate:\n"
            f"\t> domain_size: {candidate.domain_size}\n"
            f"\t> max_time: {candidate.max_time}\n"
            f"\t> dt_diffusion: {candidate.dt_diffusion}\n"
            f"\t> dt_mechanics: {candidate.dt_mechanics}\n"
            f"\t> dt_phenotype: {candidate.dt_phenotype}\n"
            f"\t> num_threads: {candidate.num_threads}\n"
            f"\t> diffusion_coefficient: {candidate.diffusion_coefficient}\n"
            f"\t> speed: {candidate.speed}\n"
            f"\t> intracellular_dt: {candidate.intracellular_dt}\n"
        )
        log_file.flush()
        start_time = time.time()
        std, delta_time_seconds = run_sampling(subjects, contexts, candidate)
        time_global = time.time() - start_time
        log_file.write(
            f"Result:\n"
            f"\t> std: {std}\n"
            f"\t> delta_time_seconds: {delta_time_seconds}\n"
            f"\t> time_global: {time_global}\n"
        )
        log_file.flush()

    log_file.write(f"\n\Finished: all candidates processed.\n")
    log_file.close()

if __name__ == "__main__":
    # Run the sampling process
    import sys
    #setup()
    run_candidates()