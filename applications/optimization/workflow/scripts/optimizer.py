import argparse
import shutil

from initial_positions import InitialPosition
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
import time
import os
from physiboss import RemotePhysiboss
from scipy.optimize import differential_evolution
import random
import multiprocessing
from fitness_functions import SquaredFitness, SpatialFitnessType
import multiprocessing

# Job execution config - parsed from CLI
TEMP_OUTPUT_DIR = None
POLLING_ATTEMPTS = None
POLLING_INTERVAL_SECONDS = None
BOOLEAN_MODEL_POOL = None
REMOTE_HPC_RESULTS_PATH = None
REMOTE_HPC_FAILED_PATH = None
HPC_TEMP_PATH = None
HPC_LOGIN = None
HPC_SCRIPT_NAME = None

# Optimization settings - parsed from CLI
OUTPUT_DIR = None
MODEL_FAMILY = None 
MODEL_NAME = None
OPTIMIZATION_BUDGET = None
REAL_FITNESS_ESTIMATION_BUDGET = None


PHYSIBOSS_DIR_LOCK = multiprocessing.Lock()

def executor(protocol: Protocols, model: ModelParameters, settings: SimulationParameters) -> float:
    job_name = f"optimization_n{time.time()}_{random.randint(0,10000)}"
    try:
        physiboss = RemotePhysiboss(
            boolean_model_pool = BOOLEAN_MODEL_POOL,
            remote_hpc_results_path = REMOTE_HPC_RESULTS_PATH,
            remote_hpc_failed_path = REMOTE_HPC_FAILED_PATH,
            hpc_temp_path = HPC_TEMP_PATH,
            hpc_login = HPC_LOGIN,
            hpc_script_name = HPC_SCRIPT_NAME
        )
        
        output = physiboss.run_remote_with_polling(
            model, protocol, job_name, settings, TEMP_OUTPUT_DIR, POLLING_ATTEMPTS, POLLING_INTERVAL_SECONDS, PHYSIBOSS_DIR_LOCK
        )

        if output is None:
            print(f"Job {job_name} failed or timed out.")
            return None
        
        squared = SquaredFitness(
            center = (60, 0),
            side_length = 80,
            fitness_type=SpatialFitnessType.LINEAR
        ).fitness(os.path.join(output, "final_cells"))
        return squared
    except Exception as e:
        print(f"Error running job {job_name}: {e}")
        return None
    finally:
        # Clean up remote job output directory
        if output and os.path.isdir(output):
            shutil.rmtree(output, ignore_errors=True)
            
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

# Global variables to track optimization events
def make_shared_counters():
    mgr = multiprocessing.Manager()
    return {
        "lock": mgr.Lock(),
        "num_function_evaluations": mgr.Value("i", 0),
        "num_individuals_evaluated": mgr.Value("i", 0),
        "num_soft_failed_jobs": mgr.Value("i", 0),
        "num_hard_failed_jobs": mgr.Value("i", 0),
        "individuals_evaluated": mgr.list()  # To store evaluated individuals if needed
    }


def fitness(arr, model: ModelParameters, settings: SimulationParameters, counters) -> float:
    with counters["lock"]:
        counters["num_individuals_evaluated"].value += 1

    protocol = array_to_protocol(arr)
    tries = 0
    while True:
        with counters["lock"]:
            counters["num_function_evaluations"].value += 1

        fit = executor(protocol, model, settings)
        if fit is not None:
            counters["individuals_evaluated"].append((arr, fit))  # Store the evaluated individual and its fitness
            return fit

        if tries >= 4:
            with counters["lock"]:
                counters["num_hard_failed_jobs"].value += 1
            counters["individuals_evaluated"].append((arr, float("inf")))  # Store the evaluated individual and its fitness
            return float("inf")

        with counters["lock"]:
            counters["num_soft_failed_jobs"].value += 1
        tries += 1


class AbstractOptimizer:
    def __init__(
        self,
        algo_name: str,
        boolean_family: str,
        boolean_model: str,
        function_evaluation_budget: int,
        real_fitness_estimation_budget: int
    ):
        self.model_parameters = ModelParameters(
            boolean_family=boolean_family,
            boolean_model=boolean_model
        )
        self.function_evaluation_budget = function_evaluation_budget
        self.real_fitness_estimation_budget = real_fitness_estimation_budget
        self.physiboss_settings = SimulationParameters.get_defaults()
        self.optimization_round_name = f"{algo_name}_budget{function_evaluation_budget}_realfitness{real_fitness_estimation_budget}_{boolean_family}_{boolean_model}"
        self.output_dir = os.path.join(OUTPUT_DIR, self.optimization_round_name)
        os.makedirs(self.output_dir, exist_ok=True)

        # Data structures to save ad the end of the optimization
        self.fitness_by_gen = []
        self.solution_by_gen = []
        self.start_time = time.time()
        self.num_function_evaluations = 0
        self.num_individuals_evaluated = 0
        self.num_soft_failed_jobs = 0
        self.num_hard_failed_jobs = 0
        self.measured_best_fitness = float('inf')
        self.refined_best_fitness = float('inf')

    def save(self):
        # Save fitness_by_gen as a CSV file
        fitness_csv_path = os.path.join(self.output_dir, "fitness_by_gen.csv")
        with open(fitness_csv_path, "w") as f:
            for gen in self.fitness_by_gen:
                for fitness in gen:
                    f.write(f"{fitness},")
                f.write("\n")
        # Solution_by_gen is a threed list (gen -> individual -> protocol parameters), can save it as a JSON file
        import json
        import numpy as np
        json_ready_data = [[item.tolist() for item in sublist] for sublist in self.solution_by_gen]

        solution_path = os.path.join(self.output_dir, "solution_by_gen.json")
        with open(solution_path, "w") as f:
            json.dump(json_ready_data, f)
        # Save other relevant info in a yaml file
        import yaml
        info_yaml_path = os.path.join(self.output_dir, "info.yaml")
        info = {
            "total_time_seconds": time.time() - self.start_time,
            "num_function_evaluations": self.num_function_evaluations,
            "num_individuals_evaluated": self.num_individuals_evaluated,
            "num_soft_failed_jobs": self.num_soft_failed_jobs,
            "num_hard_failed_jobs": self.num_hard_failed_jobs,
            "measured_best_fitness": self.measured_best_fitness,
            "refined_best_fitness": self.refined_best_fitness
        }
        with open(info_yaml_path, "w") as f:
            yaml.dump(info, f)

    def optimize(self):
        raise NotImplementedError("Subclasses must implement this method")


class DEOptimizer(AbstractOptimizer):

    def __init__(self,
        boolean_family: str,
        boolean_model: str,
        function_evaluation_budget: int,
        real_fitness_estimation_budget: int, 
        pop_size=8, 
        mutation_factor=0.15, 
        crossover_prob=0.7
    ):
        super().__init__("DE", boolean_family, boolean_model, function_evaluation_budget, real_fitness_estimation_budget)
        self.pop_size = pop_size
        self.mutation_factor = mutation_factor
        self.crossover_prob = crossover_prob
        self.max_iter = (function_evaluation_budget // (pop_size*12)) - 1
        self.bounds = [
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


    def optimize(self):
        shared_counters = make_shared_counters()
        def callback(intermediate_result):
            individuals_evaluated = shared_counters["individuals_evaluated"]
            print("Finished generation: ", len(self.fitness_by_gen), "Evaluated individuals in this generation: ", len(individuals_evaluated))
            individuals_evaluated = [x[0] for x in individuals_evaluated]  # Extract just the protocol parameters
            fitness_evaluated = [x[1] for x in individuals_evaluated]  # Extract just the fitness values
            self.fitness_by_gen.append(fitness_evaluated)
            self.solution_by_gen.append(individuals_evaluated)
            # Reset the shared list for the next generation
            with shared_counters["lock"]:
                del shared_counters["individuals_evaluated"][:]

        

        result = differential_evolution(
            fitness,
            self.bounds,
            popsize=self.pop_size,
            mutation=self.mutation_factor,
            recombination=self.crossover_prob,
            callback=callback,
            workers=32,
            args=(self.model_parameters, self.physiboss_settings, shared_counters),
            maxiter=self.max_iter,
        )
        callback(None)  # Final callback to save the last generation's data
        print("Finished optimization. Now refining the results with real fitness estimation...")
        self.measured_best_fitness = float(result.fun)
        print("Accessing shared values")
        self.num_function_evaluations = shared_counters["num_function_evaluations"].value
        self.num_individuals_evaluated = shared_counters["num_individuals_evaluated"].value
        self.num_soft_failed_jobs = shared_counters["num_soft_failed_jobs"].value
        self.num_hard_failed_jobs = shared_counters["num_hard_failed_jobs"].value

        # Refine the best solution by running it multiple times and taking the average fitness
        refineds = []
        print("Refining best solution with multiple evaluations...")
        for _ in range(self.real_fitness_estimation_budget):
            print(f"Refinement run {_+1}/{self.real_fitness_estimation_budget}...")
            refineds.append(fitness(result.x, self.model_parameters, self.physiboss_settings, shared_counters))
        refineds = [r for r in refineds if r is not None and r != float('inf')]
        self.refined_best_fitness = sum(refineds) / len(refineds) if refineds else float('inf')
        

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run remote Physiboss job configuration")
    parser.add_argument("--model-family", required=True, help="Family of the model to use from the boolean model pool")
    parser.add_argument("--model-name", required=True, help="Name of the model to use from the boolean model pool")
    parser.add_argument("--output-dir", required=True, help="Directory to store output results")
    parser.add_argument("--optimization-budget", type=int, required=True, help="Optimization budget (number of evaluations)")
    parser.add_argument("--real-fitness-estimation-budget", type=int, required=True, help="Budget for real fitness estimation (number of runs)")

    parser.add_argument("--polling-attempts", type=int, required=True, help="Number of polling attempts to wait for job completion")
    parser.add_argument("--polling-interval-seconds", type=int, required=True, help="Seconds between polling checks")
    parser.add_argument("--boolean-model-pool", required=True, help="Remote boolean model pool path")
    parser.add_argument("--remote-hpc-results-path", required=True, help="Remote path where results are stored")
    parser.add_argument("--remote-hpc-failed-path", required=True, help="Remote path where failed job outputs are stored")
    parser.add_argument("--hpc-temp-path", required=True, help="Remote temp path for HPC jobs")
    parser.add_argument("--hpc-login", required=True, help="HPC login/host")
    parser.add_argument("--hpc-script-name", required=True, help="HPC job script name")
    parser.add_argument("--temp-output-dir", required=True, help="Output directory")
    return parser.parse_args()


def main() -> None:
    global OUTPUT_DIR, POLLING_ATTEMPTS, POLLING_INTERVAL_SECONDS, TEMP_OUTPUT_DIR, MODEL_FAMILY, MODEL_NAME, OPTIMIZATION_BUDGET, REAL_FITNESS_ESTIMATION_BUDGET
    global BOOLEAN_MODEL_POOL, REMOTE_HPC_RESULTS_PATH, REMOTE_HPC_FAILED_PATH, HPC_TEMP_PATH, HPC_LOGIN, HPC_SCRIPT_NAME

    args = _parse_args()

    OUTPUT_DIR = args.output_dir
    POLLING_ATTEMPTS = args.polling_attempts
    POLLING_INTERVAL_SECONDS = args.polling_interval_seconds
    BOOLEAN_MODEL_POOL = args.boolean_model_pool
    REMOTE_HPC_RESULTS_PATH = args.remote_hpc_results_path
    REMOTE_HPC_FAILED_PATH = args.remote_hpc_failed_path
    HPC_TEMP_PATH = args.hpc_temp_path
    HPC_LOGIN = args.hpc_login
    HPC_SCRIPT_NAME = args.hpc_script_name
    TEMP_OUTPUT_DIR = args.temp_output_dir
    MODEL_FAMILY = args.model_family
    MODEL_NAME = args.model_name
    OPTIMIZATION_BUDGET = args.optimization_budget
    REAL_FITNESS_ESTIMATION_BUDGET = args.real_fitness_estimation_budget

    optimizer = DEOptimizer(
        boolean_family=MODEL_FAMILY,
        boolean_model=MODEL_NAME,
        function_evaluation_budget=OPTIMIZATION_BUDGET,
        real_fitness_estimation_budget=REAL_FITNESS_ESTIMATION_BUDGET,
        pop_size=14,
        mutation_factor=0.15,
        crossover_prob=0.7
    )
    optimizer.optimize()
    optimizer.save()

if __name__ == "__main__":
    main()
