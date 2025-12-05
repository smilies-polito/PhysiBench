import os
MaBoSS_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MaBoSS-linux64/MaBoSS")


def compare_states(s1, s2):
    return len(s1.symmetric_difference(s2))

def compare_trajectories(tr1, tr2):
    i = 0; j = 0
    diff = 0
    while(True):
        diff += compare_states(tr1[i], tr2[j])
        if (i < len(tr1)-1):
            i += 1
        if (j < len(tr2)-1):
            j += 1
        if (i == len(tr1)-1 and j == len(tr2)-1):
            break
    return diff/max(len(tr1), len(tr2))

def parse_trajectory(path):
    states = []
    with open(path, 'r') as f:
        for line in f:
            if not (line.strip() and line.strip()[0].isdigit()):
                continue 
            content = line.strip().split('\t')[1]
            states.append(set(content.strip().split(" -- ")))
    return states

def run_maboss_and_get_states(file, temp_dir):
    os.system(f"{MaBoSS_path} -c {file}.cfg -o {temp_dir}/ {file}.bnd")
    return parse_trajectory(f"{temp_dir}/_traj.txt")

if __name__ == "__main__":
    tr1 = parse_trajectory("/home/users/masera/proj/boolean/MaBoSS-linux64/OUT/OUT_traj copy 2.txt")
    tr2 = parse_trajectory("/home/users/masera/proj/boolean/MaBoSS-linux64/OUT/OUT_traj.txt")
    print(compare_trajectories(tr1, tr2))