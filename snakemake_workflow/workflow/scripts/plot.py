import subprocess
import os
import pandas as pd
import matplotlib.pyplot as plt
from pctk import multicellds
import numpy as np


def alive_cells(output_folder):
    # Creating a MCDS reader
    reader = multicellds.MultiCellDS(output_folder=output_folder)

    # Creating an iterator to load a cell DataFrame for each stored simulation time step
    df_iterator = reader.cells_as_frames_iterator()

    step_alive = []
    step_apoptotic = []
    step_necrotic = []
    time_steps = []
    print("\n")

    for (t, df_cells) in df_iterator:
        alive = (df_cells.current_phase==14).sum()
        apoptotic = (df_cells.current_phase==100).sum()
        necrotic = (df_cells.current_phase==101).sum()
        step_alive.append(alive)
        step_apoptotic.append(apoptotic)
        step_necrotic.append(necrotic)
        time_steps.append(t)
        print(f"Total alive {alive}, necrotic {necrotic} and apoptotic {apoptotic} cells at time {t}")
    
    pos = (df_cells[['x_position', 'y_position', 'z_position', 'current_phase']].values).tolist()

    
    return time_steps, step_alive, step_apoptotic, step_necrotic, pos

def plot(output_folder, time_steps, step_alive, step_necrotic, step_apoptotic, pos, resistance=False, stop_time=None, stop=False):
    # Use Set1 colormap for colors
    cmap = plt.get_cmap('Set1')
    color_alive = cmap(0)
    color_necrotic = cmap(1)
    color_apoptotic = cmap(2)
    color_resistant = cmap(3)  # Only used if resistance is True

    # Plotting the data
    fig, ax = plt.subplots(figsize=(16, 8))

    if resistance:
        df = pd.read_csv('../model/output/resistant_cells.txt', header=None)
        resistant_cells = df.values.flatten().tolist()
        if stop:
            resistant_cells.pop(round(stop_time/30))

        # Create stackplot with resistance
        ax.stackplot(time_steps, list(np.array(step_alive)-np.array(resistant_cells)), resistant_cells, step_necrotic, step_apoptotic, colors=[color_alive, color_resistant, color_necrotic, color_apoptotic], labels=['Alive Cells', 'Resistant Cells', 'Necrotic Cells', 'Apoptotic Cells'])
    else:
        # Create stackplot without resistance
        ax.stackplot(time_steps, step_alive, step_necrotic, step_apoptotic, colors=[color_alive, color_necrotic, color_apoptotic], labels=['Alive Cells', 'Necrotic Cells', 'Apoptotic Cells'])

    if stop_time is not None:
        ax.axvline(x=stop_time, color='black', linestyle='--', label='Stop Time')

    # Increase font size and use Set1 colormap
    ax.set_xlabel('Time (min)', fontsize=10)
    ax.set_ylabel('Number of Cells', fontsize=10)
    ax.set_title('Cell Population over Time', fontsize=10)
    ax.set_xticks(list(range(0, time_steps[-1], 150)))
    ax.tick_params(axis='both', which='major', labelsize=10)
    ax.legend(fontsize=15)
    ax.grid(True)

    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(os.path.join(output_folder, 'cell_population_over_time.pdf'))



if __name__ == '__main__':
    output_dir = '../bin/PhysiCell/output'
    time_steps, step_alive, step_apoptotic, step_necrotic, pos = alive_cells(output_dir)
    plot(output_dir, time_steps, step_alive, step_necrotic, step_apoptotic, pos, resistance=False, stop_time=None, stop=False)
