import numpy as np
import sys
import os
from boolean_model_mutation import *
#from MaBoSS_trajectory import *
from run_simulation import *
from distances import CorrelationDistances, EuclideanDistance
from utils import print_and_log, set_log_Path

MAX_ERRORS = 10

def run_simulation_(cfg_filename, bnd_filename, out_dir):
    with open(cfg_filename, 'r') as cfg_file:
        with open(bnd_filename, 'r') as bnd_file:
            boolean_model = BooleanModel()
            boolean_model.import_from_bnd(bnd_file, cfg_file)
            boolean_model.make_generic()
            temp_dir = out_dir + "temp_boolean_model"
            save_to_file(boolean_model, temp_dir)
            try:
                states = run_simulation(temp_dir, "temp_boolean_model")
            except Exception as e:
                os.remove(temp_dir + ".bnd")
                os.remove(temp_dir + ".cfg")
                raise e
            os.remove(temp_dir + ".bnd")
            os.remove(temp_dir + ".cfg")
            
            return boolean_model, states

def create_generics(cfg_filename, bnd_filename, out_dir, target):
    distances = CorrelationDistances()
    pool = 0
    errors = 0
    tries = 0
    while(pool < target):
        tries += 1
        if tries > target * 100:
            print_and_log("Too many tries without success, giving up.")
            return

        try:
            boolean_model, states = run_simulation_(cfg_filename, bnd_filename, out_dir)
        except KeyboardInterrupt:
            exit()
        except:
            print_and_log("Error during simulation")
            errors += 1
            if errors > MAX_ERRORS:
                print_and_log("Too many errors, giving up.")
                return
            continue

        errors = 0
        if np.count_nonzero(states) / states.size < 0.05:
            print("Too many zeros")
            continue

        if pool == 0:
            distances.add_element(states)
            save_to_file(boolean_model, out_dir + f"P{pool}")
            pool += 1
            continue

        dist = distances.test_element(states)
        if dist >= 0.2:
            save_to_file(boolean_model, out_dir + f"P{pool}")
            pool += 1
            distances.add_element(states)



if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python make_boolean_model_generic.py <path_to_original_models> <path_to_output_dir> <target_number_of_boolean_models>")
        sys.exit(1)

    original_path = sys.argv[1]
    output_path = sys.argv[2]
    target_count = int(sys.argv[3])

    # Iterate over all models in the original path
    all_subdirectories = os.listdir(original_path)
    print(f"Found {len(all_subdirectories)} models to process:\n\t{', '.join(all_subdirectories)}")
    for model_file in os.listdir(original_path):
        cfg_file = os.path.join(original_path, model_file, model_file+".cfg")
        bnd_file = os.path.join(original_path, model_file, model_file+".bnd")
        if not os.path.isfile(cfg_file) or not os.path.isfile(bnd_file):
            print(f"Skipping {model_file}: missing .cfg or .bnd file.")
            continue
        output_path_model = os.path.join(output_path, model_file)
        os.makedirs(output_path_model, exist_ok=True)
        print(f"Processing model: {model_file}")
        create_generics(
            cfg_file,
            bnd_file,
            output_path_model,
            target_count
        )
