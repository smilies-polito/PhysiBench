import multiprocessing.pool
import multiprocessing.shared_memory
from protocol_mutations import *
import networkx as nx
import numpy as np
import netrd
import matplotlib.pyplot as plt
from multiprocessing import Pool, shared_memory

NUM_PROCESSES = None

def get_matrix_from_path(file_path):
    with open(f"{file_path}.bnd", 'r') as bnd_file:
        with open(f"{file_path}.cfg", 'r') as cfg_file:
            protocol = Protocol()
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

def run_distance(args):
    m1, m2, type, max_len, skip_len_ajust = args
    if (max_len is None):
        max_len = max(m1.shape[0], m2.shape[0])
    if (skip_len_ajust):
        max_len = m1.shape[0]
    g1 = matrix_to_graph(m1, max_len)
    if (skip_len_ajust):
        max_len = m2.shape[0]
    g2 = matrix_to_graph(m2, max_len)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return get_lambda(type)(g1, g2)


def pairwise_distance(vector_of_matrices, type, max_len_global, skip_len_ajust=False):
    distances = np.zeros((len(vector_of_matrices), len(vector_of_matrices)))
    for i in range(len(vector_of_matrices)):
        for j in range(i+1, len(vector_of_matrices)):
            m1 = vector_of_matrices[i]
            m2 = vector_of_matrices[j]
            dist = run_distance((m1, m2, type, max_len_global, skip_len_ajust))
            distances[i][j] = dist
            distances[j][i] = dist
        print(i, len(vector_of_matrices))
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
    

def main():
    import sys 
    import os
    import random
    import copy
    global NUM_PROCESSES
    path = sys.argv[1]
    path = os.path.abspath(path)
    NUM_PROCESSES = int(sys.argv[2])
    num_params = len(sys.argv)
    MAX_GRAPHS_PER_TYPE = int(sys.argv[3])
    USE_GLOBAL = int(sys.argv[4])!=0

    dirs_in_path = [
        d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))
    ]
    files = []
    family = []

    out_dir_name = "static_distance"
    if (USE_GLOBAL):
        out_dir_name = "static_distance_global"
    out_dir = os.path.join(path, out_dir_name)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    for dir in dirs_in_path:
        dir_path = os.path.join(path, dir)
        files_ = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        files_ = [f for f in files_ if f.endswith(".bnd")]
        files_ = [f[:-4] for f in files_]
        files_ = [os.path.join(dir_path, f) for f in files_]
        random.shuffle(files_)
        files_ = files_[:MAX_GRAPHS_PER_TYPE]
        files = files + files_
        family.append(len(files))

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

    for p in range(5, num_params):
        type = sys.argv[p]
        print(type)
        try:
            _ = get_lambda(type)
        except ValueError:
            print(f"Unknown distance type: {type}")
            continue
        print(f"Calculating {type} distance", "Skip len ajust", type=="IpsenMikhailov"and not max_len_global)

        distances = pairwise_distance(matrices.copy(), type, max_len_global, type=="IpsenMikhailov"and not max_len_global) #1m18.673s
        #distances = pairwise_distance_multiprocess(matrices.copy(), type, max_len_global)# 4 cpu: 5m27.186s
        np.save(os.path.join(path, f"{out_dir}/distances_{type}.npy"), distances)
        with open(os.path.join(path, f"{out_dir}/distances_order_{type}.txt"), 'w') as f:
            for file in files:
                f.write(f"{file}\n")
        plot_heatmap(distances, os.path.join(path, f"{out_dir}/distances_{type}.png"), family)

def test_shuffle(files, type, n_shuffles=8):
    family = []
    matrices = []
    for index, f in enumerate(files):
        for _ in range(n_shuffles):
            with open(f"{f}.bnd", 'r') as bnd_file:
                with open(f"{f}.cfg", 'r') as cfg_file:
                    protocol = Protocol()
                    protocol.import_from_bnd(bnd_file, cfg_file)
                    protocol.to_conjunctive_form()
                    m = protocol.to_graph_matrix(shuffle_nodes=True)
                    matrices.append(m)
        family.append(index*n_shuffles)

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

if __name__ == "__main__":
    main()