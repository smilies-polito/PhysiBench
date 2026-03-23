import argparse
import math
import os
import json
import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import PCA

# Global variables
OUTPUT_DIR = None
OPT_DIR = None


def plot_average_fitness_by_generation(fitness):
    fitness_cleaned = [
        [x for x in generation if isinstance(x, float) and math.isfinite(x)] 
        for generation in fitness
    ]
    averages = [sum(gen) / len(gen) for gen in fitness_cleaned if gen]
    generations = list(range(len(averages)))

    plt.figure(figsize=(10, 6))
    plt.plot(generations, averages, label='Average Fitness', color='blue')
    plt.title('Average Fitness by Generation')
    plt.xlabel('Generation')
    plt.ylabel('Fitness')
    plt.grid(True)
    plt.legend()
    
    save_path = os.path.join(OUTPUT_DIR, "avg_fitness_by_gen.png")
    plt.savefig(save_path)
    plt.close()
    print(f"Saved average fitness plot to {save_path}")

def plot_best_fitness_by_generation(fitness):
    bests = [min(gen) for gen in fitness if gen]
    generations = list(range(len(bests)))

    plt.figure(figsize=(10, 6))
    plt.plot(generations, bests, label='Best Fitness', color='green')
    plt.title('Best Fitness by Generation')
    plt.xlabel('Generation')
    plt.ylabel('Fitness')
    plt.grid(True)
    plt.legend()
    
    save_path = os.path.join(OUTPUT_DIR, "best_fitness_by_gen.png")
    plt.savefig(save_path)
    plt.close()
    print(f"Saved best fitness plot to {save_path}")

def read_fitness_csv():
    csv_path = os.path.join(OPT_DIR, "fitness_by_gen.csv")
    fitness_data = []
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not find fitness file at {csv_path}")

    with open(csv_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                values = [float(x) for x in line.split(',') if x.strip()]
                fitness_data.append(values)
    
    return fitness_data

def read_solutions_json():
    """Reads the JSON file containing the population's parameters over generations."""
    json_path = os.path.join(OPT_DIR, "solution_by_gen.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Could not find solutions file at {json_path}")
        
    with open(json_path, 'r') as f:
        return json.load(f)

def process_pca_and_diversity(solutions):
    """
    Fits a PCA on the INITIAL generation only to set a static baseline, 
    transforms all individuals to 2D, and calculates spatial diversity per generation.
    """
    if not solutions or not solutions[0]:
        return [], []

    pca = PCA(n_components=2)
    
    # 1. Fit PCA ONLY on the first generation (static baseline)
    pca.fit(solutions[0])

    pca_data_by_gen = []
    diversity_scores = []

    # 2. Transform per generation and calculate diversity
    for gen in solutions:
        if not gen:
            pca_data_by_gen.append(np.array([]))
            diversity_scores.append(0.0)
            continue
            
        # Transform subsequent generations using the initial generation's axes
        gen_pca = pca.transform(gen)
        pca_data_by_gen.append(gen_pca)
        
        # Diversity metric: Mean distance to the generation's centroid
        centroid = np.mean(gen_pca, axis=0)
        distances = np.linalg.norm(gen_pca - centroid, axis=1)
        mean_distance = np.mean(distances)
        diversity_scores.append(mean_distance)

    return pca_data_by_gen, diversity_scores

def plot_diversity_over_time(diversity_scores):
    """Plots the population diversity metric over generations."""
    generations = list(range(len(diversity_scores)))

    plt.figure(figsize=(10, 6))
    plt.plot(generations, diversity_scores, marker='o', linestyle='-', color='purple')
    plt.title('Population Diversity (Mean Distance to Centroid) by Generation')
    plt.xlabel('Generation')
    plt.ylabel('Diversity Score')
    plt.grid(True)
    
    save_path = os.path.join(OUTPUT_DIR, "diversity_by_gen.png")
    plt.savefig(save_path)
    plt.close()
    print(f"Saved diversity plot to {save_path}")

def plot_population_evolution_3d(pca_data_by_gen):
    """Creates a 3D scatter plot of the population's 2D PCA traits over time."""
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    for gen_idx, gen_pca in enumerate(pca_data_by_gen):
        if len(gen_pca) == 0:
            continue
            
        x = gen_pca[:, 0]
        y = gen_pca[:, 1]
        z = np.full(len(x), gen_idx)  # Time dimension
        
        ax.scatter(x, y, z, alpha=0.5, s=10)

    ax.set_xlabel('PCA 1 (Baseline)')
    ax.set_ylabel('PCA 2 (Baseline)')
    ax.set_zlabel('Generation (Time)')
    ax.set_title('Evolution of Population over Time')
    
    save_path = os.path.join(OUTPUT_DIR, "pca_evolution_3d.png")
    plt.savefig(save_path)
    plt.close()
    print(f"Saved 3D PCA evolution plot to {save_path}")


# --- MAIN SETUP ---

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get plots for an optimization run")
    parser.add_argument("--output-dir", required=True, help="Directory to store output results")
    return parser.parse_args()

def main() -> None:
    global OUTPUT_DIR, OPT_DIR
    args = _parse_args()

    raw_dir = args.output_dir
    if not os.path.isdir(raw_dir):
        raise Exception(f"Output directory {raw_dir} not found or not a directory")
    
    OPT_DIR = os.path.join(raw_dir, os.path.split(raw_dir.rstrip('/'))[1].replace("raw_", "").replace("__", "_"))
    if not os.path.isdir(OPT_DIR):
        raise Exception(f"Optimization run directory {OPT_DIR} not found or not a directory")
    
    OUTPUT_DIR = os.path.join(raw_dir, "plots")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Legacy fitness plots
    fitness = read_fitness_csv()
    plot_best_fitness_by_generation(fitness)
    plot_average_fitness_by_generation(fitness)

    # New PCA and Diversity plots
    solutions = read_solutions_json()
    pca_data_by_gen, diversity_scores = process_pca_and_diversity(solutions)
    
    plot_diversity_over_time(diversity_scores)
    plot_population_evolution_3d(pca_data_by_gen)


if __name__ == "__main__":
    main()