import numpy as np
import sys
import os
from protocol_mutations import *
from MaBoSS_trajectory import *
from run_simulation import *
import matplotlib.pyplot as plt
from distances import CorrelationDistances, EuclideanDistance
from utils import print_and_log, set_log_Path

MAX_ERRORS = 10

def run_simulation_(cfg_filename, bnd_filename, out_dir):
    with open(cfg_filename, 'r') as cfg_file:
        with open(bnd_filename, 'r') as bnd_file:
            protocol = Protocol()
            protocol.import_from_bnd(bnd_file, cfg_file)
            protocol.make_generic()
            save_to_file(protocol, out_dir + "/temp/temp_protocol")
            states = run_simulation(out_dir+"/temp", "temp_protocol")
            
            return protocol, states

def create_generics(cfg_filename, bnd_filename, out_dir, target):
    distances = CorrelationDistances()
    pool = 0
    errors = 0
    while(pool < target):
        print("Running simulation")
        try:
            protocol, states = run_simulation_(cfg_filename, bnd_filename, out_dir)
        except KeyboardInterrupt:
            exit()
        except:
            print_and_log("Error during simulation")
            errors += 1
            if errors > MAX_ERRORS:
                print_and_log("Too many errors, exiting")
                exit()
            continue
        errors = 0
        print(states)
        if np.count_nonzero(states) / states.size < 0.05:
            print("Too many zeros")
            continue
        if pool == 0:
            print("Adding first one")
            distances.add_element(states)
            save_to_file(protocol, out_dir + f"P{pool}")
            pool += 1
            continue
        dist = distances.test_element(states)
        print(dist)
        if dist >= 0.2:
            print("Save!")
            save_to_file(protocol, out_dir + f"P{pool}")
            pool += 1
            distances.add_element(states)



if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python make_protocol_generic.py <path_to_directory> <name_of_protocol> <path_to_out_dir> <target_number_of_protocols>")
        sys.exit(1)
    path = sys.argv[1]
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
    base_name = sys.argv[2]
    target = int(sys.argv[4])
    out_dir = sys.argv[3]
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), out_dir)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    if not os.path.exists(out_dir+"/temp"):
        os.makedirs(out_dir+"/temp")
    
    #Open protocol
    cfg_file = os.path.join(path, base_name+".cfg")
    bnd_file = os.path.join(path, base_name+".bnd")
    create_generics(cfg_file, bnd_file, out_dir, target)