import numpy as np
import sys
import os
from boolean_model_mutation import *
from distances import CorrelationDistances, EuclideanDistance
from utils import print_and_log, set_log_Path
from physiboss import LocalPhysiboss
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
from pctk import multicellds
MAX_ERRORS = 10

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

def run_simulation_(cfg_filename, bnd_filename, out_dir):
    config_results = []
    with open(cfg_filename, 'r') as cfg_file:
        with open(bnd_filename, 'r') as bnd_file:
            boolean_model = BooleanModel()
            boolean_model.import_from_bnd(bnd_file, cfg_file)
            boolean_model.make_generic()
            temp_dir = out_dir + "/_temp_boolean_model"
            save_to_file(boolean_model, temp_dir)
            
            try:
                for protocol in POOL_OF_PROTOCOLS:
                    n_tries = 0
                    while(True):
                        try:
                            # Run the simulation
                            model = ModelParameters(
                                out_dir.split("/")[-1],
                                "_temp_boolean_model"
                            )
                            sim_params = SimulationParameters.get_test_defaults()
                            pool_path = os.path.dirname(out_dir)
                            output_dir = LocalPhysiboss.run_local(model, protocol, sim_params, pool_path)
                            alive = alive_cells(output_dir)
                            alive = np.array(alive)
                            alive = alive[-6:]
                            config_results.append(alive)
                            break

                        except Exception as e:
                            print(f"Exception at try: {n_tries}")
                            print(e)
                            print(f"protocol:",
                                protocol.treatment_duration,
                                protocol.treatment_period,
                                protocol.xmin,
                                protocol.xmax,
                                protocol.ymin,
                                protocol.ymax,
                                protocol.initial_positions.type,
                                protocol.initial_positions.density,
                                protocol.initial_positions.mode,
                                protocol.initial_positions.center,
                                protocol.initial_positions.length,
                            )
                            n_tries += 1
                            if n_tries > 2:
                                raise e
            except Exception as e:
                print("Exception:", e)
                raise e
            finally:
                os.remove(temp_dir + ".bnd")
                os.remove(temp_dir + ".cfg")
            config_results = np.array(config_results)
            return boolean_model, config_results

def create_generics(cfg_filename, bnd_filename, out_dir, target):
    distances = CorrelationDistances()
    pool = 0
    errors = 0
    tries = 0
    while(pool < target):
        print_and_log(f"Creating generic boolean model {pool+1}/{target} - tries {tries}")
        tries += 1
        if tries > target * 100:
            print_and_log("Too many tries without success, giving up.")
            return

        try:
            boolean_model, states = run_simulation_(cfg_filename, bnd_filename, out_dir)
            print(f"States: {states}")
        except KeyboardInterrupt:
            exit()
        except Exception as e:
            print_and_log("Error during simulation - retrying.")
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
            print_and_log("First model, adding to pool without distance check.")
            distances.add_element(states)
            save_to_file(boolean_model, out_dir + f"/P{pool}")
            pool += 1
            continue

        dist = distances.test_element(states)
        if dist >= 0.2:
            print_and_log(f"Distance {dist:.3f} is above threshold, adding model to pool.")
            save_to_file(boolean_model, out_dir + f"/P{pool}")
            pool += 1
            distances.add_element(states)
            continue 
        print(f"Distance too small ({dist}), retrying. This was try n. {tries} for model {pool+1}/{target}.")


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
    if len(sys.argv) != 4:
        print("Usage: python make_boolean_model_generic.py <path_to_original_models> <path_to_output_dir> <target_number_of_boolean_models>")
        sys.exit(1)

    original_path = sys.argv[1]
    output_path = sys.argv[2]
    target_count = int(sys.argv[3])

    set_log_Path(os.path.join(output_path, "make_model_generic.log"))

    print("Testing the random test protocols before starting the generation of generic models.",
        "Defective protocols will be replaced with new ones until all protocols are working.")
    test_and_fix_test_proticols(original_path)
    print("All protocols are working, starting the generation of generic models.")

    # Iterate over all models in the original path
    all_subdirectories = os.listdir(original_path)
    print(f"Found {len(all_subdirectories)} models to process:\n\t{', '.join(all_subdirectories)}")
    for model_file in os.listdir(original_path):
        print(f"Processing model: {model_file}")
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
