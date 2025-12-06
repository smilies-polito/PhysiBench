from boolean_model_mutation.py import *
from run_simulation import *
from distances import CorrelationDistances, EuclideanDistance
from utils import print_and_log, set_log_Path

import numpy as np
import sys
import os


MIN_DIST = 0.15
MAX_TESTED = 200000

MUTATION_P = [
    0.15,  #Switch nodes logic
    0.26,   #Replace logical operator
    0.228,  #Replace node inside logic
    0.25,   #Negate subexpression
    0.01,   #add_input_to_logic 
    0.002,    #Add node
    0.1,     #randomize_node_logic
    0.00    #randomize parameter
]

MAX_CREATED_NODES = 45
MIN_MUTATIONS = 10
MAX_MUTATIONS = 2000

def mutate(file, temp_dir, N_ITER, created_nodes=0):
    n_added = 0
    print(f"Mutating {file}")
    with open(f"{file}.bnd", 'r') as bnd_file:
        with open(f"{file}.cfg", 'r') as cfg_file:
            protocol = Protocol()
            protocol.import_from_bnd(bnd_file, cfg_file)
            for _ in range(N_ITER):
                operation = np.random.choice(
                    [protocol.switch_nodes_logic, protocol.replace_logical_operator, 
                        protocol.replace_node_inside_logic, protocol.negate_subexpression,
                        protocol.add_input_to_logic, protocol.add_new_node, protocol.randomize_node_logic,
                        protocol.randomize_parameter], 
                    p=MUTATION_P)
                if operation == protocol.add_new_node:
                    if created_nodes+n_added >= MAX_CREATED_NODES:
                        continue
                    n_added += 1
                operation()
            save_to_file(protocol, temp_dir + "/tmp_protocol")
    return n_added

class OpenedProtocol:
    def __init__(self, name, out_dir):
        self.name = name
        self.out_dir = out_dir
        self.simulation_states = None
        self.created_nodes = 0
    
    def get_mutated_protocol(self, N_ITER):
        temp_path = os.path.join(self.out_dir, "temp")
        n_added = mutate(os.path.join(self.out_dir, self.name), temp_path, N_ITER, self.created_nodes)
        p = OpenedProtocol("tmp_protocol", temp_path)
        p.created_nodes = self.created_nodes + n_added
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
        #run_maboss_and_get_states(directory + "/temp/tmp_protocol", directory + "/temp")

#Linear distance measure
def linear_distance_single_step(p1, p2):
    # p1, p2 are 1D numpy arrays
    return np.linalg.norm(p1 - p2)
def linear_distance_flattened(p1, p2):
    # p1, p2 are 2D numpy arrays
    return linear_distance_single_step(p1.flatten(), p2.flatten()) / p1.shape[0]

def run(directory, target, protocols_pool):
    distances = CorrelationDistances()
    for base_pool in protocols_pool.keys():
        for protocol in protocols_pool[base_pool]:
            distances.add_element(protocol.simulation_states)
            target -= 1
    num_tested = 0
    n_iter = MIN_MUTATIONS
    while(target > 0 and num_tested < MAX_TESTED):
        num_tested += 1
        print_and_log("Testing new protocol - " + str(target) + f" - {n_iter} iterations")
        candidate_pool = np.random.choice(list(protocols_pool.keys()))
        candidate = np.random.choice(protocols_pool[candidate_pool])
        protocol = candidate.get_mutated_protocol(n_iter)
        try:
            protocol.get_physiboss_states()
        except KeyboardInterrupt:
            exit()
        except:
            print_and_log("Error during simulation")
            continue
        min_dist = distances.test_element(protocol.simulation_states)
        print_and_log("Min correlation distance: " + str(min_dist))
        #euclidean_distances = EuclideanDistance.test_element([p.simulation_states for p in protocols_pool], protocol.simulation_states)
        #print_and_log("Euclidean distances: " + str(euclidean_distances))
        if (min_dist > MIN_DIST):
            n_iter = max(int(n_iter*0.75), MIN_MUTATIONS)
            print_and_log("Adding to pool")
            protocol.rename(os.path.join(directory, candidate_pool), f"V{len(protocols_pool[candidate_pool])}")
            protocol.export_simulation_states()
            protocols_pool[candidate_pool].append(protocol)
            distances.add_element(protocol.simulation_states)
            target -= 1
        else:
            print_and_log("Discard")
            n_iter = min(int(n_iter*1.5), MAX_MUTATIONS)
    print_and_log("Finished. Number of tested protocols: " + str(num_tested))
    

def init_new(target_path, pool_path):
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
                protocol_basename = file[:-4]
                #Copy base_name.cfg and base_name.bnd to OUT directory
                cfg_file = os.path.join(pool_path, base_pool, protocol_basename+".cfg")
                bnd_file = os.path.join(pool_path, base_pool, protocol_basename+".bnd")
                os.system(f"cp {cfg_file} {target_path}/{base_pool}/V{i}.cfg")
                os.system(f"cp {bnd_file} {target_path}/{base_pool}/V{i}.bnd")
                protocol = OpenedProtocol(f"V{i}", os.path.join(target_path, base_pool))
                protocol.get_physiboss_states()
                protocol.export_simulation_states()
                pool[base_pool].append(protocol)
                i += 1
    return pool 


def restore(target_path):
    protocols_pool = {}
    for base_pool in os.listdir(target_path):
        protocols_pool[base_pool] = []
        for file in os.listdir(os.path.join(target_path, base_pool)):
            if file.endswith(".cfg"):
                protocol_basename = file[:-4]
                file_path = os.path.join(target_path, base_pool, protocol_basename + ".bnd")
                process_result = subprocess.run(f"cat {file_path} | grep -c 'NODE_[0-9]\\+'", shell=True, capture_output=True, text=True)
                number_created_nodes = int(process_result.stdout.strip())
                protocol = OpenedProtocol(protocol_basename, os.path.join(target_path, base_pool))
                protocol.created_nodes = number_created_nodes
                protocol.simulation_states = np.loadtxt(os.path.join(target_path, base_pool, protocol_basename + "_states.csv"), delimiter="\t")
                protocols_pool[base_pool].append(protocol)
    return protocols_pool


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python create_variants.py <target_directory> <pool_directory> <target_number_protocols>")
        sys.exit(1)

    target_path = sys.argv[1]
    pool_path = sys.argv[2]
    target = int(sys.argv[3])

    if (os.path.exists(target_path)):
        pool = restore(target_path)
        set_log_Path(os.path.join(target_path, "logs.txt"))
    else:
        pool = init_new(target_path, pool_path)
        set_log_Path(os.path.join(target_path, "logs.txt"))
        print_and_log(f"Starting new process.")
    run(target_path, target, pool)
