from initial_positions import Cell, InitialPosition
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
from physiboss import RemotePhysiboss, run_command
import time
import os
import argparse
import matplotlib.pyplot as plt
from scipy.optimize import differential_evolution
import random
import multiprocessing
from fitness_functions import AliveCellsFitness, SquaredFitness, SpatialFitnessType
import multiprocessing
import shutil


PHYSIBOSS_DIR_LOCK = multiprocessing.Lock()

TEMP_OUTPUT_DIR = None
POLLING_ATTEMPTS = 20
POLLING_INTERVAL_SECONDS = 15
BOOLEAN_MODEL_POOL = None
REMOTE_HPC_RESULTS_PATH = None
REMOTE_HPC_FAILED_PATH = None
HPC_TEMP_PATH = None
HPC_LOGIN = None
HPC_SCRIPT_NAME = None

def executor(protocol: Protocols, model: ModelParameters, settings: SimulationParameters) -> float:
    job_name = f"optimization_n{time.time()}_{random.randint(0,10000)}"
    print("Submitting job:", job_name)

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
            return float('inf')  # Return a high fitness value for failed jobs
        
        squared = SquaredFitness(
            center = (60, 0),
            side_length = 80,
            fitness_type=SpatialFitnessType.LINEAR
        ).fitness(os.path.join(output, "final_cells"))

        print(f"Job {job_name} completed with fitness: {squared}")
    except Exception as e:
        print(f"Error running job {job_name}: {e}")
        return float('inf')  # Return a high fitness value for exceptions
    finally:
        if output and os.path.isdir(output):
            shutil.rmtree(output, ignore_errors=True)


def run_some_tests():
    simulation_settings = SimulationParameters.get_defaults()
    models = [
        ModelParameters("cell_cycle", "P0"),
    ]
    protocols = [
        Protocols.get_random() for _ in range(3)
    ]
    with multiprocessing.Pool(processes=len(protocols)*len(models)) as pool:
        results = []
        for model in models:
            for protocol in protocols:
                result = pool.apply_async(executor, args=(protocol, model, simulation_settings))
                results.append(result)
        
        # Wait for all results to complete
        for result in results:
            fitness = result.get()
            print("Fitness:", fitness)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run remote Physiboss job configuration")
    parser.add_argument("--output-dir", default=TEMP_OUTPUT_DIR, help="Local output directory (or None)")
    parser.add_argument("--polling-attempts", type=int, default=POLLING_ATTEMPTS, help="Number of polling attempts to wait for job completion")
    parser.add_argument("--polling-interval-seconds", type=int, default=POLLING_INTERVAL_SECONDS, help="Seconds between polling checks")
    parser.add_argument("--boolean-model-pool", default=BOOLEAN_MODEL_POOL, help="Remote boolean model pool path")
    parser.add_argument("--remote-hpc-results-path", default=REMOTE_HPC_RESULTS_PATH, help="Remote path where results are stored")
    parser.add_argument("--remote-hpc-failed-path", default=REMOTE_HPC_FAILED_PATH, help="Remote path where failed job outputs are stored")
    parser.add_argument("--hpc-temp-path", default=HPC_TEMP_PATH, help="Remote temp path for HPC jobs")
    parser.add_argument("--hpc-login", default=HPC_LOGIN, help="HPC login/host")
    parser.add_argument("--hpc-script-name", default=HPC_SCRIPT_NAME, help="HPC job script name")
    return parser.parse_args()


def main() -> None:
    global TEMP_OUTPUT_DIR, POLLING_ATTEMPTS, POLLING_INTERVAL_SECONDS
    global BOOLEAN_MODEL_POOL, REMOTE_HPC_RESULTS_PATH, REMOTE_HPC_FAILED_PATH, HPC_TEMP_PATH, HPC_LOGIN, HPC_SCRIPT_NAME

    args = _parse_args()

    TEMP_OUTPUT_DIR = args.output_dir
    POLLING_ATTEMPTS = args.polling_attempts
    POLLING_INTERVAL_SECONDS = args.polling_interval_seconds
    BOOLEAN_MODEL_POOL = args.boolean_model_pool
    REMOTE_HPC_RESULTS_PATH = args.remote_hpc_results_path
    REMOTE_HPC_FAILED_PATH = args.remote_hpc_failed_path
    HPC_TEMP_PATH = args.hpc_temp_path
    HPC_LOGIN = args.hpc_login
    HPC_SCRIPT_NAME = args.hpc_script_name

    print("Configured remote Physiboss settings:")
    print(f"  TEMP_OUTPUT_DIR={TEMP_OUTPUT_DIR}")
    print(f"  POLLING_ATTEMPTS={POLLING_ATTEMPTS}")
    print(f"  POLLING_INTERVAL_SECONDS={POLLING_INTERVAL_SECONDS}")
    print(f"  BOOLEAN_MODEL_POOL={BOOLEAN_MODEL_POOL}")
    print(f"  REMOTE_HPC_RESULTS_PATH={REMOTE_HPC_RESULTS_PATH}")
    print(f"  REMOTE_HPC_FAILED_PATH={REMOTE_HPC_FAILED_PATH}")
    print(f"  HPC_TEMP_PATH={HPC_TEMP_PATH}")
    print(f"  HPC_LOGIN={HPC_LOGIN}")
    print(f"  HPC_SCRIPT_NAME={HPC_SCRIPT_NAME}")

    os.makedirs(TEMP_OUTPUT_DIR, exist_ok=True)

    run_some_tests()


if __name__ == "__main__":
    main()
