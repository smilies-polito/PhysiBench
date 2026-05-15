from boolean_model_mutation import *
from distances import CorrelationDistances
from utils import print_and_log, set_log_Path
import numpy as np
import os
import argparse
from pctk import multicellds
from physiboss import LocalPhysiboss
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters

NUM_TESTING_PROTOCOLS = 48
POOL_OF_PROTOCOLS = [
    Protocols.get_random() for _ in range(NUM_TESTING_PROTOCOLS)
]

def alive_cells(output_folder):
    # Creating a MCDS reader
    reader = multicellds.MultiCellDS(output_folder=output_folder)
    # Creating an iterator to load a cell DataFrame for each stored simulation time step
    df_iterator = reader.cells_as_frames_iterator()
    step_alive = []
    time_steps = []

    for (t, df_cells) in df_iterator:
        alive = (df_cells.current_phase==14).sum()
        step_alive.append(alive)
        time_steps.append(t)
    return step_alive

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
    def __init__(self, name, out_dir, max_created_nodes):
        self.name = name
        self.out_dir = out_dir
        self.simulation_states = None
        self.created_nodes = 0
        self.max_created_nodes = max_created_nodes
    
    def get_mutated_boolean_model(self, N_ITER):
        temp_path = os.path.join(self.out_dir, "temp")
        n_added = mutate(os.path.join(self.out_dir, self.name), temp_path, N_ITER, self.created_nodes, self.max_created_nodes)
        p = OpenedModel("tmp_boolean_model", temp_path, self.max_created_nodes)
        p.created_nodes = self.created_nodes + n_added
        p.max_created_nodes = self.max_created_nodes
        return p
    
    def get_physiboss_states(self):
        has_errors = False
        states = []
        for protocol in POOL_OF_PROTOCOLS:
            try:
                # Run the simulation
                model = ModelParameters(
                    self.out_dir.split("/")[-1],
                    self.name
                )
                sim_params = SimulationParameters.get_test_defaults()
                pool_path = os.path.dirname(self.out_dir)
                output_dir = LocalPhysiboss.run_local(model, protocol, sim_params, pool_path)
                alive = alive_cells(output_dir)
                alive = np.array(alive)
                alive = alive[-6:]
                states.append(alive)
            except Exception as e:
                print("Failed simulation")
                states.append(np.array([0]*20))
                has_errors = True
        self.simulation_states = states
        return has_errors
    
    def rename(self, base_path, name):
        os.system(f"mv {self.out_dir}/{self.name}.cfg {base_path}/{name}.cfg")
        os.system(f"mv {self.out_dir}/{self.name}.bnd {base_path}/{name}.bnd")
        self.name = name
        self.out_dir = base_path
    
    def export_simulation_states(self):
        np.savetxt(os.path.join(self.out_dir, self.name + "_states.csv"), self.simulation_states, delimiter="\t")

#Linear distance measure
def linear_distance_single_step(p1, p2):
    # p1, p2 are 1D numpy arrays
    return np.linalg.norm(p1 - p2)
def linear_distance_flattened(p1, p2):
    # p1, p2 are 2D numpy arrays
    return linear_distance_single_step(p1.flatten(), p2.flatten()) / p1.shape[0]

def run(directory, target, boolean_models_pool, min_dist=0.15, max_tested=200000, min_mutations=10, max_mutations=2000):
    print("RUN")
    print(f"Starting run: target={target}, min_dist={min_dist}, max_tested={max_tested}, max tested={max_tested}")
    distances = CorrelationDistances()
    for base_pool in boolean_models_pool.keys():
        print(f"Adding base pool {base_pool} to distances. {len(boolean_models_pool[base_pool])} models.")
        for boolean_model in boolean_models_pool[base_pool]:
            distances.add_element(boolean_model.simulation_states)
            target -= 1
    num_tested = 0
    n_iter = min_mutations
    print(f"Starting run: target={target}, min_dist={min_dist}, max_tested={max_tested}, max tested={max_tested}")
    while(target > 0 and num_tested < max_tested):
        print(f"Num tested: {num_tested}, Target remaining: {target}")
        num_tested += 1
        print_and_log("Testing new boolean_model - " + str(target) + f" - {n_iter} iterations")
        candidate_pool = np.random.choice(list(boolean_models_pool.keys()))
        candidate = np.random.choice(boolean_models_pool[candidate_pool])
        boolean_model = candidate.get_mutated_boolean_model(n_iter)
        try:
            has_errors = boolean_model.get_physiboss_states()
            print(f"Has errors: {has_errors}")
            if has_errors:
                print(f"Simulation errors - num_tested: {num_tested}, target: {target}")
                continue
        except KeyboardInterrupt:
            exit()
        except:
            print_and_log("Error during simulation")
            continue
        
        min_dist_val = distances.test_element(boolean_model.simulation_states)
        print_and_log("Min correlation distance: " + str(min_dist_val))
        #euclidean_distances = EuclideanDistance.test_element([p.simulation_states for p in boolean_models_pool], boolean_model.simulation_states)
        #print_and_log("Euclidean distances: " + str(euclidean_distances))
        if (not has_errors and min_dist_val > min_dist):
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
        if not (os.path.isdir(os.path.join(pool_path, base_pool))):
            print(f"Skipping {base_pool}, not a directory")
            continue
        os.makedirs(os.path.join(target_path, base_pool))
        os.makedirs(os.path.join(target_path, base_pool, "temp"))
        i = 0
        pool[base_pool] = []
        for file in os.listdir(os.path.join(pool_path, base_pool)):
            if file.endswith(".cfg"):
                n_errors = 0
                while(True):
                    boolean_model_basename = file[:-4]
                    #Copy base_name.cfg and base_name.bnd to OUT directory
                    print(f"Simulating: {boolean_model_basename}, {file}")
                    cfg_file = os.path.join(pool_path, base_pool, boolean_model_basename+".cfg")
                    bnd_file = os.path.join(pool_path, base_pool, boolean_model_basename+".bnd")
                    os.system(f"cp {cfg_file} {target_path}/{base_pool}/V{i}.cfg")
                    os.system(f"cp {bnd_file} {target_path}/{base_pool}/V{i}.bnd")
                    print(f"Created base model {boolean_model_basename}, file {file}, copied in {target_path}/{base_pool}/V{i}.cfg")
                    boolean_model = OpenedModel(f"V{i}", os.path.join(target_path, base_pool), max_created_nodes)
                    boolean_model.max_created_nodes = max_created_nodes
                    has_errors = boolean_model.get_physiboss_states()
                    if (has_errors):
                        n_errors += 1
                        if n_errors < 3:
                            print(f"Simulation errors in base model {boolean_model_basename}, file {file}, re-trying...")
                        else:
                            print(f"Too many errors with base model {boolean_model_basename}, file {file}")
                            raise Exception("Simulation errors in base model.")
                    else:
                        break
                boolean_model.export_simulation_states()
                pool[base_pool].append(boolean_model)
                i += 1
    return pool 

def test_and_fix_test_proticols(original_path):


    global POOL_OF_PROTOCOLS

    # Find any random model
    families = os.listdir(original_path)
    if len(families) == 0:
        print("No models found in the original path.")
        return
    family = families[0]
    models = os.listdir(os.path.join(original_path, family))
    if len(models) == 0:
        print("No models found in the original path.")
        return
    model_name = models[0][:-4] # remove .cfg or .bnd extension

    def test_protocol(protocol):
        # Run the simulation
        try:
            model = ModelParameters(
                family,
                model_name
            )
            sim_params = SimulationParameters.get_test_defaults()
            _ = LocalPhysiboss.run_local(model, protocol, sim_params, original_path)
        except Exception as e:
            print(e)
            return False 
        return True

    for i in range(len(POOL_OF_PROTOCOLS)):
        while True:
            protocol = POOL_OF_PROTOCOLS[i]
            is_working = test_protocol(protocol)
            if is_working:
                break
            else:
                print(f"Protocol {i} is not working, replacing with a new one.")
                POOL_OF_PROTOCOLS[i] = Protocols.get_random()
        

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
    
    test_and_fix_test_proticols(args.pool_directory)

    # Set global MUTATION_P (used by mutate function)
    MUTATION_P = args.mutation_probs

    if os.path.exists(args.target_directory):
        print("Directory exists already")
        exit()
    else:
        print("Creating new pool")
        pool = init_new(args.target_directory, args.pool_directory, args.max_created_nodes)
        set_log_Path(os.path.join(args.target_directory, "logs.txt"))
        print_and_log(f"Starting new process.")
    
    print(
        "Starting process with:\n",
        "* Target dir:", args.target_directory,
        "\n * Target number: ", args.target_number
    )
    run(args.target_directory, args.target_number, pool, 
        min_dist=args.min_dist, max_tested=args.max_tested,
        min_mutations=args.min_mutations, max_mutations=args.max_mutations)
