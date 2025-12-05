from fitness_functions import AliveCellsFitness, CircularFitness, SpatialFitnessType, SquaredFitness
import os
import numpy as np

N_PROCESSES = 48

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

def fitness_for_job(job_name: str):
    path = "/job_directory/" + job_name + "/output/final_cells.mat"
    output_path = "/out_directory/" + job_name + "_fitness.csv"
    fitness_scores = []
    try:
        for fitness in fitnesses:
            fitness_scores.append(fitness.fitness(path))
    except Exception as e:
        fitness_scores = [np.nan] * len(fitnesses)
    with open(output_path, "w") as file:
        for f in fitness_scores:
            file.write(f"{f}\n")


# List files in "/job_directory":
jobs = os.listdir("/job_directory")
print("Running jobs in batch. Found jobs:", len(jobs))
import multiprocessing
with multiprocessing.Pool(processes=N_PROCESSES) as pool:
    pool.map(fitness_for_job, jobs)
