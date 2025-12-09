from boolean_model_mutation.py import *
from run_simulation import *
from distances import CorrelationDistances, EuclideanDistance
from utils import print_and_log, set_log_Path
import numpy as np
import sys
import os
import argparse
import subprocess

"""
This script creates new Boolean model variants by mutating existing models.
"""

# Global variable for mutation probabilities (set via command line)
MUTATION_P = None

def mutate(file, temp_dir, N_ITER, created_nodes=0, max_created_nodes=45):
    n_added = 0
    print(f"Mutating {file}")
    with open(f"{file}.bnd", 'r') as bnd_file:
        with open(f"{file}.cfg", 'r') as cfg_file:
            boolean_model = BooleanModel()
            boolean_model.import_from_bnd(bnd_file, cfg_file)
            for _ in range(N_ITER):
                operation = np.random.choice(
                    [boolean_model.switch_nodes_logic, boolean_model.replace_logical_operator, 
                        boolean_model.replace_node_inside_logic, boolean_model.negate_subexpression,
                        boolean_model.add_input_to_logic, boolean_model.add_new_node, boolean_model.randomize_node_logic,
                        boolean_model.randomize_parameter], 
                    p=MUTATION_P)
                if operation == boolean_model.add_new_node:
                    if created_nodes+n_added >= max_created_nodes:
                        continue
                    n_added += 1
                operation()
            save_to_file(boolean_model, temp_dir + "/tmp_boolean_model")
    return n_added

class OpenedModel:
    def __init__(self, name, out_dir):
        self.name = name
        self.out_dir = out_dir
        self.simulation_states = None
        self.created_nodes = 0
        self.max_created_nodes = MAX_CREATED_NODES
    
    def get_mutated_boolean_model(self, N_ITER):
        temp_path = os.path.join(self.out_dir, "temp")
        n_added = mutate(os.path.join(self.out_dir, self.name), temp_path, N_ITER, self.created_nodes, self.max_created_nodes)
        p = OpenedModel("tmp_boolean_model", temp_path)
        p.created_nodes = self.created_nodes + n_added
        p.max_created_nodes = self.max_created_nodes
        return p
    
    def get_physiboss_states(self):
        self.simulation_states = run_simulation(self.out_dir, self.name)
    
    def rename(self, base_path, name):
        os.system(f"mv {self.out_dir}/{self.name}.cfg {base_path}/{name}.cfg")
        os.system(f"mv {self.out_dir}/{self.name}.bnd {base_path}/{name}.bnd")
        self.name = name
        self.out_dir = base_path
    
    def export_simulation_states(self):
        np.savetxt(os.path.join(self.out_dir, self.name + "_states.csv"), self.simulation_states, delimiter="\t")
    
    def get_maboss_states(self):
        assert False #Not used for now
        #run_maboss_and_get_states(directory + "/temp/tmp_boolean_model", directory + "/temp")

#Linear distance measure
def linear_distance_single_step(p1, p2):
    # p1, p2 are 1D numpy arrays
    return np.linalg.norm(p1 - p2)
def linear_distance_flattened(p1, p2):
    # p1, p2 are 2D numpy arrays
    return linear_distance_single_step(p1.flatten(), p2.flatten()) / p1.shape[0]

def run(directory, target, boolean_models_pool, min_dist=0.15, max_tested=200000, min_mutations=10, max_mutations=2000):
    distances = CorrelationDistances()
    for base_pool in boolean_models_pool.keys():
        for boolean_model in boolean_models_pool[base_pool]:
            distances.add_element(boolean_model.simulation_states)
            target -= 1
    num_tested = 0
    n_iter = min_mutations
    while(target > 0 and num_tested < max_tested):
        num_tested += 1
        print_and_log("Testing new boolean_model - " + str(target) + f" - {n_iter} iterations")
        candidate_pool = np.random.choice(list(boolean_models_pool.keys()))
        candidate = np.random.choice(boolean_models_pool[candidate_pool])
        boolean_model = candidate.get_mutated_boolean_model(n_iter)
        try:
            boolean_model.get_physiboss_states()
        except KeyboardInterrupt:
            exit()
        except:
            print_and_log("Error during simulation")
            continue
        min_dist_val = distances.test_element(boolean_model.simulation_states)
        print_and_log("Min correlation distance: " + str(min_dist_val))
        #euclidean_distances = EuclideanDistance.test_element([p.simulation_states for p in boolean_models_pool], boolean_model.simulation_states)
        #print_and_log("Euclidean distances: " + str(euclidean_distances))
        if (min_dist_val > min_dist):
            n_iter = max(int(n_iter*0.75), min_mutations)
            print_and_log("Adding to pool")
            boolean_model.rename(os.path.join(directory, candidate_pool), f"V{len(boolean_models_pool[candidate_pool])}")
            boolean_model.export_simulation_states()
            boolean_models_pool[candidate_pool].append(boolean_model)
            distances.add_element(boolean_model.simulation_states)
            target -= 1
        else:
            print_and_log("Discard")
            n_iter = min(int(n_iter*1.5), max_mutations)
    print_and_log("Finished. Number of tested boolean_models: " + str(num_tested))
    

def init_new(target_path, pool_path, max_created_nodes=45):
    if not os.path.exists(target_path):
        os.makedirs(target_path)
    if not os.path.exists(target_path+"/temp"):
        os.makedirs(target_path+"/temp")
    base_pools = os.listdir(pool_path)
    pool = {}
    #Create directories corresponding to base pools
    for base_pool in base_pools:
        os.makedirs(os.path.join(target_path, base_pool))
        os.makedirs(os.path.join(target_path, base_pool, "temp"))
        i = 0
        pool[base_pool] = []
        for file in os.listdir(os.path.join(pool_path, base_pool)):
            if file.endswith(".cfg"):
                boolean_model_basename = file[:-4]
                #Copy base_name.cfg and base_name.bnd to OUT directory
                cfg_file = os.path.join(pool_path, base_pool, boolean_model_basename+".cfg")
                bnd_file = os.path.join(pool_path, base_pool, boolean_model_basename+".bnd")
                os.system(f"cp {cfg_file} {target_path}/{base_pool}/V{i}.cfg")
                os.system(f"cp {bnd_file} {target_path}/{base_pool}/V{i}.bnd")
                boolean_model = OpenedModel(f"V{i}", os.path.join(target_path, base_pool))
                boolean_model.max_created_nodes = max_created_nodes
                boolean_model.get_physiboss_states()
                boolean_model.export_simulation_states()
                pool[base_pool].append(boolean_model)
                i += 1
    return pool 


def restore(target_path, max_created_nodes=45):
    boolean_models_pool = {}
    for base_pool in os.listdir(target_path):
        boolean_models_pool[base_pool] = []
        for file in os.listdir(os.path.join(target_path, base_pool)):
            if file.endswith(".cfg"):
                boolean_model_basename = file[:-4]
                file_path = os.path.join(target_path, base_pool, boolean_model_basename + ".bnd")
                process_result = subprocess.run(f"cat {file_path} | grep -c 'NODE_[0-9]\\+'", shell=True, capture_output=True, text=True)
                number_created_nodes = int(process_result.stdout.strip())
                boolean_model = OpenedModel(boolean_model_basename, os.path.join(target_path, base_pool))
                boolean_model.created_nodes = number_created_nodes
                boolean_model.max_created_nodes = max_created_nodes
                boolean_model.simulation_states = np.loadtxt(os.path.join(target_path, base_pool, boolean_model_basename + "_states.csv"), delimiter="\t")
                boolean_models_pool[base_pool].append(boolean_model)
    return boolean_models_pool


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Create Boolean model variants by mutating existing models.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Required arguments
    parser.add_argument('target_directory', type=str,
                        help='Directory where variants will be created')
    parser.add_argument('pool_directory', type=str,
                        help='Directory containing the pool of base models')
    parser.add_argument('target_number', type=int,
                        help='Target number of Boolean models to generate')
    
    # Optional arguments for configuration
    parser.add_argument('--min-dist', type=float, default=0.15,
                        help='Minimum correlation distance threshold')
    parser.add_argument('--max-tested', type=int, default=200000,
                        help='Maximum number of models to test')
    parser.add_argument('--max-created-nodes', type=int, default=45,
                        help='Maximum number of created nodes allowed')
    parser.add_argument('--min-mutations', type=int, default=10,
                        help='Minimum number of mutations per iteration')
    parser.add_argument('--max-mutations', type=int, default=2000,
                        help='Maximum number of mutations per iteration')
    
    # Mutation probabilities
    parser.add_argument('--mutation-probs', type=float, nargs=8,
                        default=[0.15, 0.26, 0.228, 0.25, 0.01, 0.002, 0.1, 0.00],
                        metavar=('SWITCH', 'REPLACE_OP', 'REPLACE_NODE', 'NEGATE', 
                                'ADD_INPUT', 'ADD_NODE', 'RANDOMIZE_LOGIC', 'RANDOMIZE_PARAM'),
                        help='Mutation probabilities: switch_nodes_logic replace_logical_operator '
                             'replace_node_inside_logic negate_subexpression add_input_to_logic '
                             'add_new_node randomize_node_logic randomize_parameter')
    
    args = parser.parse_args()
    
    # Validate mutation probabilities sum to ~1.0
    prob_sum = sum(args.mutation_probs)
    if not (0.99 <= prob_sum <= 1.01):
        print(f"Warning: Mutation probabilities sum to {prob_sum}, not 1.0. Normalizing...")
        args.mutation_probs = [p / prob_sum for p in args.mutation_probs]
    
    # Set global MUTATION_P (used by mutate function)
    global MUTATION_P
    MUTATION_P = args.mutation_probs

    if os.path.exists(args.target_directory):
        pool = restore(args.target_directory, args.max_created_nodes)
        set_log_Path(os.path.join(args.target_directory, "logs.txt"))
    else:
        pool = init_new(args.target_directory, args.pool_directory, args.max_created_nodes)
        set_log_Path(os.path.join(args.target_directory, "logs.txt"))
        print_and_log(f"Starting new process.")
    
    run(args.target_directory, args.target_number, pool, 
        min_dist=args.min_dist, max_tested=args.max_tested,
        min_mutations=args.min_mutations, max_mutations=args.max_mutations)
