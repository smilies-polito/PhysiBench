import multiprocessing.pool
import multiprocessing.shared_memory
import multiprocessing as mp

from boolean_model_mutation import *
import networkx as nx
import numpy as np
import netrd
import matplotlib.pyplot as plt
from multiprocessing import Pool, shared_memory
import argparse
import os
from tqdm import tqdm

NUM_PROCESSES = None

def get_matrix_from_path(file_path):
    with open(f"{file_path}.bnd", 'r') as bnd_file:
        with open(f"{file_path}.cfg", 'r') as cfg_file:
            protocol = BooleanModel()
            protocol.import_from_bnd(bnd_file, cfg_file)
            protocol.to_conjunctive_form()
            m = protocol.to_graph_matrix()
            return m
        
def matrix_to_graph(matrix, max_len):
    # Create an empty graph
    matrix = matrix + 1
    DG = nx.DiGraph()
    for i in range(max_len):
        DG.add_node(i)
    # Add edges based on the adjacency matrix
    for i in range(len(matrix)):
        for j in range(i + 1, len(matrix)):
            if matrix[i][j] != 0:
                DG.add_weighted_edges_from([(i, j, matrix[i][j])])
    return DG


import warnings

def _run_distance_pair(args):
    """
    args = (i, j, m1, m2, type, max_len, skip_len_adjust)
    """
    i, j, m1, m2, dist_type, max_len, skip_len_adjust = args
    name = f"{i}-{j}"
    print("Starting", name)

    # Adjust lengths
    if max_len is None:
        max_len = max(m1.shape[0], m2.shape[0])
    if skip_len_adjust:
        max_len = m1.shape[0]
    g1 = matrix_to_graph(m1, max_len)

    if skip_len_adjust:
        max_len = m2.shape[0]
    g2 = matrix_to_graph(m2, max_len)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        print("Running lambda", name)
        lambda_ = get_lambda(dist_type)
        x = lambda_(g1, g2)
        return (i, j, x)


def pairwise_distance(vector_of_matrices, dist_type, max_len_global, skip_len_adjust=False):
    tasks = []

    # Build argument list sending *matrix copies* only for (i, j)
    for i in range(len(vector_of_matrices)):
        for j in range(i + 1, len(vector_of_matrices)):
            m1 = vector_of_matrices[i]
            m2 = vector_of_matrices[j]

            tasks.append(
                (i, j, m1, m2, dist_type, max_len_global, skip_len_adjust)
            )

    print(f"Computing {len(tasks)} pairwise distances...")

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=NUM_PROCESSES) as pool:
        results = list(tqdm(pool.imap(_run_distance_pair, tasks)))

    # Build distance matrix
    n = len(vector_of_matrices)
    distances = np.zeros((n, n))

    for i, j, value in results:
        distances[i][j] = value
        distances[j][i] = value

    print("Finished")
    return distances

def plot_heatmap(distances, path, family_boundaries=None, title="", size=None, family_names=None):
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(distances, cmap='hot', interpolation='nearest')
    plt.colorbar(im)
    plt.title(f"Pairwise Distances Heatmap - {title}")
    if (size is not None):
        fig.set_size_inches(size[0], size[1])
    if family_names is not None:
        ax.set_xticks([(i+0.5)*(distances.shape[0]/len(family_names)) for i in range(len(family_names))])
        ax.set_yticks([(i+0.5)*(distances.shape[0]/len(family_names)) for i in range(len(family_names))])
        ax.set_xticklabels(family_names, rotation=90)
        ax.set_yticklabels(family_names)
    if family_boundaries is not None:
        for boundary in family_boundaries:
            # Add vertical lines
            ax.axvline(x=boundary - 0.5, color='white', linestyle='-', linewidth=1.5)
            # Add horizontal lines
            ax.axhline(y=boundary - 0.5, color='white', linestyle='-', linewidth=1.5)
    if (path is None):
        plt.show()
    else:
        plt.savefig(path)
        plt.close()

def plot_all_heatmaps(vector_of_distances, path, titles=[], N_ROWS=2, N_COLS=3, family_boundaries=None, family_names=None, title=""):
    assert len(vector_of_distances) == len(titles), "Number of distance matrices must match number of titles"
    assert N_ROWS * N_COLS >= len(vector_of_distances), "Not enough subplots for all distance matrices"
    assert family_names is None or family_boundaries is not None, "family_boundaries must be provided when family_names is set"

    def _family_segments(n_items, boundaries):
        if boundaries is None:
            return [(0, n_items)]
        internal_boundaries = sorted(set(int(b) for b in boundaries if 0 < int(b) < n_items))
        edges = [0] + internal_boundaries + [n_items]
        return [(edges[k], edges[k + 1]) for k in range(len(edges) - 1)]
    
    fig, axes = plt.subplots(
        N_ROWS,
        N_COLS,
        figsize=(N_COLS * 6, N_ROWS * 8),
    )
    axes = np.array(axes).flatten()
    
    for i, (distances, subplot_title) in enumerate(zip(vector_of_distances, titles)):
        ax = axes[i]
        im = ax.imshow(distances, cmap='hot', interpolation='nearest')
        fig.colorbar(im, ax=ax, orientation='horizontal', fraction=0.05, pad=0.16)
        ax.set_title(subplot_title, fontsize=18, pad=10)

        if family_names is None:
            # Remove numeric ticks when no semantic labels are provided.
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            segments = _family_segments(distances.shape[0], family_boundaries)
            assert len(family_names) == len(segments), f"Number of family names must match number of families defined by boundaries. For {len(segments)} segments, expected {len(segments)} family names but got {family_names}."
            centers = [((start + end - 1) / 2.0) for start, end in segments]
            ax.set_xticks(centers)
            ax.set_yticks(centers)
            ax.xaxis.tick_top()
            ax.set_xticklabels(family_names, rotation=90)
            ax.set_yticklabels(family_names)
            ax.tick_params(axis='x', which='major', labeltop=True, labelbottom=False, labelsize=10, pad=2)
            ax.tick_params(axis='y', which='major', labelsize=10)
        
        if family_boundaries is not None:
            for boundary in family_boundaries:
                # Add vertical lines
                ax.axvline(x=boundary - 0.5, color='black', linestyle='-', linewidth=1.5)
                # Add horizontal lines
                ax.axhline(y=boundary - 0.5, color='black', linestyle='-', linewidth=1.5)
    
    # Remove empty subplots
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    # Reserve a larger top band when family labels are shown on top of each heatmap.
    top_limit = 0.78 if family_names is not None else 0.88
    if title:
        fig.suptitle(title, fontsize=22, y=0.995)
        fig.tight_layout(rect=[0, 0, 1, top_limit])
    else:
        fig.tight_layout()

    if path is None:
        plt.show()
    else:
        plt.savefig(path)
        plt.close()

def get_lambda(type):
    if type == "JaccardDistance":
        return netrd.distance.JaccardDistance().dist
    elif type == "IpsenMikhailov":
        return netrd.distance.IpsenMikhailov().dist
    elif type == "ResistancePerturbation":
        return netrd.distance.ResistancePerturbation().dist
    elif type == "LaplacianSpectral":
        return netrd.distance.LaplacianSpectral().dist
    elif type == "LaplacianSpectral_Normal":
        return lambda g1, g2: netrd.distance.LaplacianSpectral().dist(g1, g2, kernel="normal")
    elif type == "PolynomialDissimilarity":
        return netrd.distance.PolynomialDissimilarity().dist
    elif type == "DeltaCon":
        return netrd.distance.DeltaCon().dist
    elif type == "QuantumJSD":
        return netrd.distance.QuantumJSD().dist
    elif type == "CommunicabilityJSD":
        return netrd.distance.CommunicabilityJSD().dist
    elif type == "dkSeries":
        return netrd.distance.dkSeries().dist
    elif type == "DMeasure":
        return netrd.distance.DMeasure().dist
    else:
        raise ValueError(f"Unknown distance type: {type}")
    

def test_shuffle(files, type, n_shuffles=8):
    family = []
    matrices = []
    for index, f in enumerate(files):
        for _ in range(n_shuffles):
            with open(f"{f}.bnd", 'r') as bnd_file:
                with open(f"{f}.cfg", 'r') as cfg_file:
                    protocol = BooleanModel()
                    protocol.import_from_bnd(bnd_file, cfg_file)
                    protocol.to_conjunctive_form()
                    m = protocol.to_graph_matrix(shuffle_nodes=True)
                    matrices.append(m)
        family.append(index*n_shuffles)
    print(f"Running distances with {type} for {len(matrices)} shuffled matrices...")
    distances = pairwise_distance(matrices, type, None)
    return distances, family

def plot_from_results(path, type):
    distances = np.load(os.path.join(path, f"distances_{type}.npy"))
    family = []
    current_f = None; count=0
    f_names = []
    with open(os.path.join(path, f"distances_order_{type}.txt"), 'r') as f:
        for line in f:
            family_name = "/".join(line.split("/")[:-1])
            if (current_f != family_name):
                family.append(count)
                current_f = family_name
                f_names.append(current_f.split("/")[-1])
            count += 1
    f_names.append(current_f.split("/")[-1])
    family = family[1:]
    plot_heatmap(distances, None, family, type, (8, 6), f_names)
    return distances, family, f_names

def test_metrics(mutated_models_path, out_dir):
    import random
    def get_one(dir):
        all_files = [f for f in os.listdir(os.path.join(mutated_models_path, dir)) if f.endswith(".bnd")]
        idx = random.randint(0, len(all_files)-1)
        return all_files[idx][:-4]
    list_of_dirs = os.listdir(mutated_models_path)
    list_of_dirs = [d for d in list_of_dirs if os.path.isdir(os.path.join(mutated_models_path, d))]
    models = [
        os.path.join(mutated_models_path, d, get_one(os.path.join(mutated_models_path, d))) for d in list_of_dirs
    ]
    def run_with(measure):
        with warnings.catch_warnings():
            distances, families = test_shuffle(models, type=measure, n_shuffles=8)
            return distances, families
    distances, families = [], []
    for measure in ["DeltaCon", "IpsenMikhailov", "QuantumJSD"]:
        d, f = run_with(measure)
        distances.append(d)
        families.append(f)
    plot_all_heatmaps(
        distances, 
        os.path.join(out_dir, f"test_distances.png"),
        titles=[
            f"Static Distances with {type}" for type in ["DeltaCon", "IpsenMikhailov", "QuantumJSD"]
        ], 
        N_ROWS=1, N_COLS=3,
        family_boundaries=families[0],
        family_names=[l.replace("_", " ") for l in list_of_dirs],
        title="Distances between shuffled versions of one protocol by family"
    )
    

def main():
    import os
    import random
    global NUM_PROCESSES
    
    parser = argparse.ArgumentParser(
        description='Calculate pairwise distances between protocol graph matrices'
    )
    parser.add_argument(
        'path',
        type=str,
        help='Path to directory containing protocol subdirectories'
    )
    parser.add_argument(
        'output_directory',
        type=str,
        help='Directory to save output distance matrices and heatmaps'
    )
    parser.add_argument(
        'num_processes',
        type=int,
        help='Number of processes to use for parallel computation'
    )
    parser.add_argument(
        'max_graphs',
        type=int,
        help='Maximum number of graphs per protocol type'
    )
    parser.add_argument(
        'use_global',
        type=int,
        choices=[0, 1],
        help='Use global maximum length (1) or individual lengths (0)'
    )
    parser.add_argument(
        'distance_types',
        nargs='+',
        help='Distance metric types to calculate (e.g., JaccardDistance, IpsenMikhailov)'
    )
    
    args = parser.parse_args()
    
    path = os.path.abspath(args.path)
    NUM_PROCESSES = args.num_processes
    MAX_GRAPHS_PER_TYPE = args.max_graphs
    USE_GLOBAL = args.use_global != 0

    dirs_in_path = [
        d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))
    ]
    files = []
    family = []

    out_dir = args.output_directory
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    print(
        "Computing distances in path:", path,
        "with", NUM_PROCESSES, "processes",
        "max graphs per type:", MAX_GRAPHS_PER_TYPE,
        "use global length:", USE_GLOBAL,
        "\nFound directories:", dirs_in_path,
        "\nWriting output in:", out_dir
    )
    for dir in dirs_in_path:
        dir_path = os.path.join(path, dir)
        files_ = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        files_ = [f for f in files_ if f.endswith(".bnd")]
        files_ = [f[:-4] for f in files_]
        files_ = [os.path.join(dir_path, f) for f in files_]
        random.shuffle(files_)
        if MAX_GRAPHS_PER_TYPE != -1:
            files_ = files_[:MAX_GRAPHS_PER_TYPE]
        files = files + files_
        family.append(len(files))

    
    test_metrics(path, out_dir)

    matrices = [
        get_matrix_from_path(f) for f in files
    ]
    if (USE_GLOBAL):
        max_len_global = max([
            len(x[0]) for x in matrices
        ])
    else:
        max_len_global = None

    print(
        "Running distances", "with", NUM_PROCESSES, "processes", "and max_len_global", max_len_global,
        "for", len(matrices), "matrices"
        )

    for type in args.distance_types:
        print(type)
        try:
            _ = get_lambda(type)
        except ValueError:
            print(f"Unknown distance type: {type}")
            continue
        print(f"Calculating {type} distance", "Skip len ajust", type=="IpsenMikhailov"and not max_len_global)

        distances = pairwise_distance(matrices.copy(), type, max_len_global, type=="IpsenMikhailov"and not max_len_global) #1m18.673s
        #distances = pairwise_distance_multiprocess(matrices.copy(), type, max_len_global)# 4 cpu: 5m27.186s
        np.save(os.path.join(out_dir,f"distances_{type}.npy"), distances)
        with open(os.path.join(out_dir, f"distances_order_{type}.txt"), 'w') as f:
            for file in files:
                f.write(f"{file}\n")
        plot_heatmap(distances, os.path.join(out_dir, f"distances_{type}.png"), family)

    # Now create the last heatmap with all the distances together
    all_distances = []
    print("Plotting all heatmaps together...")
    for type in args.distance_types:
        distances = np.load(os.path.join(out_dir, f"distances_{type}.npy"))
        all_distances.append(distances)
    print(all_distances[0].shape)
    plot_all_heatmaps(
        all_distances, 
        os.path.join(out_dir, f"distances_all.png"),
        titles=[
            f"Static Distances with {type}" for type in args.distance_types
        ], 
        N_ROWS=1, N_COLS=3,
        title="Pairwise distance between models of the dataset",
        family_boundaries=family[:-1],
        family_names=[d.replace("_", " ") for d in dirs_in_path]
        )
    
    

if __name__ == "__main__":
    main()