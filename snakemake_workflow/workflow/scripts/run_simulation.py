import os 
import subprocess
import xml.etree.ElementTree as ET
from pctk import multicellds
import numpy as np
import sys

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "model_generic_old")
print(MODEL_PATH)
CONFIG_PATH = os.path.join(MODEL_PATH, "config")
NETWORK_PATH = os.path.join(CONFIG_PATH, "boolean_network")


#Limits (300, 800) , (0, 2), (10, 300), (10, 600)
CONFIGS = [
    {"membrane_length": 450, "concentration_input_sub": 0.2, "duration_add_input_sub": 120, "time_add_input_sub": 40},
    {"membrane_length": 710, "concentration_input_sub": 0.7, "duration_add_input_sub": 60, "time_add_input_sub": 500},
    {"membrane_length": 190, "concentration_input_sub": 0.6, "duration_add_input_sub": 240, "time_add_input_sub": 480},
    {"membrane_length": 600, "concentration_input_sub": 0.4, "duration_add_input_sub": 180, "time_add_input_sub": 250},
    {"membrane_length": 300, "concentration_input_sub": 0.1, "duration_add_input_sub": 300, "time_add_input_sub": 100},
    {"membrane_length": 800, "concentration_input_sub": 0.9, "duration_add_input_sub": 10, "time_add_input_sub": 600},
    {"membrane_length": 491, "concentration_input_sub": 2, "duration_add_input_sub": 88, "time_add_input_sub": 292},
    {"membrane_length": 702, "concentration_input_sub": 0, "duration_add_input_sub": 253, "time_add_input_sub": 507},
    {"membrane_length": 565, "concentration_input_sub": 1, "duration_add_input_sub": 300, "time_add_input_sub": 311},
    {"membrane_length": 383, "concentration_input_sub": 0, "duration_add_input_sub": 209, "time_add_input_sub": 105},
    {"membrane_length": 731, "concentration_input_sub": 0, "duration_add_input_sub": 24, "time_add_input_sub": 432},
    {"membrane_length": 402, "concentration_input_sub": 1, "duration_add_input_sub": 101, "time_add_input_sub": 513}
]


def change_xml_config(membrane_length, concentration_input_sub, duration_add_input_sub, time_add_input_sub):
    tree = ET.parse(f"{CONFIG_PATH}/PhysiCell_settings.xml")
    root = tree.getroot()
    membrane_elem = root.find('.//membrane_length')
    membrane_elem.text = str(membrane_length)
    concentration_elem = root.find('.//concentration_input_sub')
    concentration_elem.text = str(concentration_input_sub)
    duration_elem = root.find('.//duration_add_input_sub')
    duration_elem.text = str(duration_add_input_sub)
    time_elem = root.find('.//time_add_input_sub')
    time_elem.text = str(time_add_input_sub)
    tree.write(f"{CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)

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

def run_simulation(path, base_name, MAX_PROTOCOLS=100):
    return [] #TEMP 
    os.system("rm -rf "+NETWORK_PATH)
    os.system(f"mkdir -p {NETWORK_PATH}")
    #Files base_name.cfg and base_name.bnd are copied to NETWORK_PATH directory
    cfg_file = os.path.join(path, base_name+".cfg")
    bnd_file = os.path.join(path, base_name+".bnd")
    os.system(f"cp {cfg_file} {NETWORK_PATH}/input_sub_conf.cfg")
    os.system(f"cp {bnd_file} {NETWORK_PATH}/input_sub_nodes.bnd")
    config_results = []
    for config in CONFIGS[:MAX_PROTOCOLS]:
        change_xml_config(config["membrane_length"], config["concentration_input_sub"], config["duration_add_input_sub"], config["time_add_input_sub"])
        # Change current working directory
        os.chdir(MODEL_PATH)
        #Cleanup
        executable_file = 'input_sub-cancer-model'
        cleanup = ["make", 'data-cleanup']
        subprocess.run(cleanup, check=True, stdout=subprocess.DEVNULL)
        #Run simulation
        execute_command = ["./" + executable_file]
        subprocess.run(execute_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        #subprocess.run(execute_command, check=True)
        al = np.array(alive_cells(f"{MODEL_PATH}/output"))
        al = al[len(al)-20:]
        config_results.append(al)
    config_results = np.array(config_results)
    return config_results




