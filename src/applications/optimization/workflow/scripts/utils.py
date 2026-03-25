import numpy as np
import os

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.txt")

def test_maboss_physicell_correlation(path):
    maboss_matrix = np.loadtxt(os.path.join(path, "distance_matrix_PhysiBoSS.csv"), delimiter=",")
    physicell_matrix = np.loadtxt(os.path.join(path, "distance_matrix_PhysiCell.csv"), delimiter=",")
    print(np.corrcoef(maboss_matrix.flatten(), physicell_matrix.flatten()))

def set_log_Path(path):
    global LOG_PATH
    LOG_PATH = path
    
def print_and_log(value):
    value = str(value)
    print(value)
    with open(LOG_PATH, "a") as f:
        f.write(value + "\n")