from initial_positions import Cell, InitialPosition
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
from physiboss import Physiboss, run_command
import time
import os
import matplotlib.pyplot as plt
from scipy.optimize import differential_evolution
import random
import multiprocessing
from fitness_functions import AliveCellsFitness, SquaredFitness, SpatialFitnessType
import multiprocessing

PHYSIBOSS_DIR_LOCK = multiprocessing.Lock()


#Physiboss config
Physiboss.BOOLEAN_MODEL_POOL = "../protocols/v1/pool" # Must contain families and models subfolders
Physiboss.PHYSIBOSS_PATH = f"../bin/PhysiCell/" # Path to PhysiCell binary folder - must contain config folder
Physiboss.REMOTE_HPC_RESULTS_PATH = "masera/results_new_dir" # Path on the HPC server where results are stored
Physiboss.HPC_TEMP_PATH = "/home/rsmeriglio/masera/jobs" # Temporary path on the HPC server for job submission
Physiboss.REMOTE_HPC_FAILED_PATH = "masera/failed_jobs" # Path on the HPC server where failed jobs are stored
# HPC script that will run the job there
hpc_script_name = "masera/run_job.sh"

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.dirname(BASE_PATH)
OUTPUT_PATH = os.path.join(BASE_PATH,"optimization_results", "squared_1")
TEMP_DATA_PATH = os.path.join(BASE_PATH,"temp_data")
os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(TEMP_DATA_PATH, exist_ok=True)

MAX_JOBS = 260

BUDGET = 8000


def executor(protocol: Protocols, model: ModelParameters, settings: SimulationParameters) -> float:
    job_name = f"optimization_n{time.time()}_{random.randint(0,10000)}"
    try:
        Physiboss.run_remote_with_lock(
            model, protocol, job_name, settings, hpc_script_name, PHYSIBOSS_DIR_LOCK
        )
        for _ in range(4*30):
            time.sleep(15)
            jobs = Physiboss.get_job_list()
            if job_name in jobs:
                try:
                    remote_hpc_job = os.path.join(Physiboss.REMOTE_HPC_RESULTS_PATH, job_name, "output")
                    local_job = os.path.join(TEMP_DATA_PATH, job_name)
                    system_command = f"scp -r rsmeriglio@hpc-lb.polito.it:{remote_hpc_job} {local_job}"
                    run_command(system_command)
                    #alive = AliveCellsFitness().fitness(os.path.join(local_job, "final_cells"))
                    squared = SquaredFitness(
                        center = (60, 0),
                        side_length = 80,
                        fitness_type=SpatialFitnessType.LINEAR
                    ).fitness(os.path.join(local_job, "final_cells"))
                    print("Job", job_name, "completed with fitness", squared)
                    return squared
                except Exception as e:
                    print("Error retrieving job", job_name, ":", e)
                    return None
                finally:
                    try:
                        run_command(f"rm -rf {local_job}")
                        run_command(f"ssh rsmeriglio@hpc-lb.polito.it rm -rf {os.path.join(Physiboss.REMOTE_HPC_RESULTS_PATH, job_name)}")
                    except:
                        print("Cannot clean up job files for", job_name)
            failed_jobs = Physiboss.get_failed_job_list()
            if job_name in failed_jobs:
                print(f"Job {job_name} failed on HPC.")
                try:
                    pass # Don't clean up failed jobs for further analysis
                    #run_command(f"ssh rsmeriglio@hpc-lb.polito.it rm -rf {os.path.join(Physiboss.REMOTE_HPC_FAILED_PATH, job_name)}")
                except:
                    print("Cannot clean up job files for", job_name)
                finally:
                    return None
        return None
    except Exception as e:
        print("Error submitting job", job_name, ":", e)
        return None

def array_to_protocol(arr) -> Protocols:
    return Protocols(
        treatment_duration=arr[0],
        treatment_period=arr[1],
        xmin=arr[2],
        xmax=arr[3],
        ymin=arr[4],
        ymax=arr[5],
        initial_positions=InitialPosition(
            type="circle" if arr[6] < 0.5 else "square",
            center=(arr[7], arr[8]),
            density=arr[9],
            cell_type=0,
            mode="sparse" if arr[10] < 0.5 else "contour",
            length=arr[11]
        )
    )

def fitness(arr, model: ModelParameters, settings: SimulationParameters) -> float:
    protocol = array_to_protocol(arr)
    tries = 0
    while(True):
        fitness = executor(protocol, model, settings)
        if fitness is not None:
            return fitness
        if (tries >= 4):
            return 1000.0
        tries += 1
        print("Retrying...")

class MainOptimizer:
    def __init__(self, name, model_settings):
        self.name = name
        self.simulation_settings = SimulationParameters.get_defaults()
        self.start_time = time.time()
        self.best_overall = []
        self.best_by_gen = []
        self.model_settings = model_settings
        self.output_path = os.path.join(OUTPUT_PATH, name)
        os.makedirs(self.output_path, exist_ok=True)
        print(f"Optimization started. Results will be saved in {self.output_path}")

    def validate(self):
        best_solution = self.best_overall[-1] if self.best_overall else None
        best_solution_array = best_solution[0] if best_solution else None
        if best_solution_array is not None:
            with multiprocessing.Pool(processes=MAX_JOBS) as pool:
                results = pool.starmap(
                    fitness,
                    [(best_solution_array, self.model_settings, self.simulation_settings) for _ in range(MAX_JOBS)]
                )
            average = sum(results) / len(results)
            print(f"Validation average fitness over 499 runs: {average}")
            return average
        else:
            return None

    def finish(self):
        average = self.validate()
        end_time = time.time()
        elapsed_time = end_time - self.start_time
        print(f"Optimization finished in {elapsed_time:.2f} seconds.")
        # Log best results to file
        with open(os.path.join(self.output_path, "best_results.txt"), "w") as f:
            f.write(f"Validation Average Fitness: {average}\n\n")
            f.write("Best Overall:\n")
            for item in self.best_overall:
                f.write(f"{item}\n")
            f.write("\nBest by Generation:\n")
            for gen, item in enumerate(self.best_by_gen):
                f.write(f"Generation {gen}:\n")
                f.write(f"{item}\n")
        with open(os.path.join(self.output_path, "log.txt"), "a") as f:
            f.write(f"Optimization finished in {elapsed_time:.2f} seconds.\n")
        # Make plots
        if self.best_by_gen:
            plt.figure()
            plt.plot(range(len(self.best_by_gen)), [b[1] for b in self.best_by_gen], marker='o')
            plt.title('Best Fitness by Generation')
            plt.xlabel('Generation')
            plt.ylabel('Best Fitness')
            plt.grid(True)
            plt.savefig(os.path.join(self.output_path, "best_fitness_by_generation.png"))
            plt.close()
        if self.best_overall:
            plt.figure()
            plt.plot(range(len(self.best_overall)), [b[1] for b in self.best_overall], marker='o', color='orange')
            plt.title('Best Overall Fitness')
            plt.xlabel('Iteration')
            plt.ylabel('Best Fitness')
            plt.grid(True)
            plt.savefig(os.path.join(self.output_path, "best_overall_fitness.png"))
            plt.close()


class DEOptimizer(MainOptimizer):

    def __init__(self, name, model_settings, pop_size=14, mutation_factor=0.15, crossover_prob=0.7):
        super().__init__(name, model_settings)
        self.pop_size = pop_size
        self.mutation_factor = mutation_factor
        self.crossover_prob = crossover_prob
        max_iter = (BUDGET // (6 * pop_size)) - 1
        bounds = [
            (0, 1), # treatment_duration
            (0, 0.5), # treatment_period
            (0, 10), # xmin
            (0, 10), # xmax
            (0, 10), # ymin
            (0, 10), # ymax
            (0, 1), # initial_positions.type
            (-100, 100), # initial_positions.center.x
            (-100, 100), # initial_positions.center.y
            (0.5, 0.8), # initial_positions.density
            (0, 1), # initial_positions.mode
            (30, 200) # initial_positions.length
        ]

        def callback(intermediate_result):
            print(f"Generation {len(self.best_by_gen)}: Best Fitness = {intermediate_result.fun}")
            self.best_by_gen.append(
                (intermediate_result.x, intermediate_result.fun)
            )
            if (self.best_overall == []) or (intermediate_result.fun < self.best_overall[-1][1]):
                self.best_overall.append((intermediate_result.x, intermediate_result.fun))
            else:
                self.best_overall.append(self.best_overall[-1])

        result = result = differential_evolution(
            fitness,
            bounds,
            popsize=self.pop_size,
            mutation=self.mutation_factor,
            recombination=self.crossover_prob,
            callback=callback,
            workers=32,
            args=(self.model_settings, self.simulation_settings),
            maxiter=max_iter,
        )



"""print(
    executor(
        Protocols(
            treatment_duration=0.5,
            treatment_period=0.1,
            xmin=0,
            xmax=10,
            ymin=0,
            ymax=10,
            initial_positions=InitialPosition(
                type="circle",
                center=(0, 0),
                density=0.5,
                cell_type=0,
                mode="sparse",
                length=100
            )
        ),
        ModelParameters(
            boolean_family="EGFTNF",
            boolean_model="V5"
        ),
        SimulationParameters.get_defaults()    
        #protocol: Protocols, model: ModelParameters, settings: SimulationParameters
    )
)"""
models = [
    ("EGFTNF", "V5"),
    #("cell_cycle", "V5"),
    ("gastric_cancer", "V14"),
    ("macrophage","V2")
]

for family, model in models:
    opt = DEOptimizer(f"{family}-{model}", ModelParameters(
        boolean_family=family,
        boolean_model=model
    ))
    opt.finish()