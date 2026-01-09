import os
from dataclasses import dataclass
import random
import subprocess
from typing import Tuple
import xml.etree.ElementTree as ET
from initial_positions import Cell, InitialPosition
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
import subprocess
        
#############################################################
#    Physiboss:
#        - Interface to run physiboss simulations with given model and protocol parameters.
#
#    Usage:
#
#        Physiboss.get_job_list() # to get the list of results already present on the HPC server.
#           * Must have specified Physiboss.REMOTE_HPC_RESULTS_PATH correctly
#############################################################
import subprocess


def run_command(command, path=None, silent=False):
    if path is None:
        path = os.getcwd()
    completed = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=path)
    if completed.returncode == 0:
        return None
    # On failure, print stdout and stderr then raise
    print("Command failed:", command)
    if not silent:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)
    raise RuntimeError(f"Command failed with exit code {completed.returncode}")

def is_singularity():
    """Check if running inside a Singularity container"""
    return 'SINGULARITY_CONTAINER' in os.environ or \
           'SINGULARITY_NAME' in os.environ

class LocalPhysiboss:
    
    NETWORK_BASE_NAME = "cellfate"
    BIN_NAME = "project"

    PHYSICELL_PATH = "../physiboss/PhysiCell/"
    CONFIG_PATH = os.path.join(PHYSICELL_PATH, "config")
    NETWORK_PATH = os.path.join(CONFIG_PATH, "simple_tnf", "boolean_network")
    
    if is_singularity():
        NETWORK_PATH = "/virtualconfig/simple_tnf/boolean_network"
        CONFIG_PATH = "/virtualconfig"
        PHYSICELL_PATH = "/bin/PhysiCell"
    
    def run_local(model: ModelParameters, protocol: Protocols, sim_params: SimulationParameters, pool_path: str):
        if (protocol is not None):
            protocol.test()
        #Remove old boolean files
        run_command("rm -rf "+LocalPhysiboss.NETWORK_PATH)
        run_command(f"mkdir -p {LocalPhysiboss.NETWORK_PATH}")

        #Set new ones
        base_path = f"{pool_path}/{model.boolean_family}/{model.boolean_model}"
        cfg_file = f"{base_path}.cfg"
        bnd_file = f"{base_path}.bnd"
        run_command(f"cp {cfg_file} {LocalPhysiboss.NETWORK_PATH}/{LocalPhysiboss.NETWORK_BASE_NAME}.cfg")
        run_command(f"cp {bnd_file} {LocalPhysiboss.NETWORK_PATH}/{LocalPhysiboss.NETWORK_BASE_NAME}.bnd")
        for ext in ['cfg', 'bnd']:
            file_path = f"{LocalPhysiboss.NETWORK_PATH}/{LocalPhysiboss.NETWORK_BASE_NAME}.{ext}"
            # Booleans were built for a different version of physiboss with 2 different nodes names.
            with open(file_path, 'r') as f:
                content = f.read()
            content = content.replace("TNF", "TNFOLD")
            content = content.replace("input_sub", "TNF")
            with open(file_path, 'w') as f:
                f.write(content)

        #Set initial positions
        initial_position_cells = protocol.initial_positions.get_cells()
        if (protocol is not None):
            cells_path = f"{LocalPhysiboss.NETWORK_PATH}/cells.csv"
            with open(cells_path, 'w') as f:
                f.write("x,y,z,type\n")
                for cell in initial_position_cells:
                    f.write(f"{cell[0]},{cell[1]},{cell[2]},{cell[3]}\n")

        #Update the XML configuration file
        tree = ET.parse(f"{LocalPhysiboss.CONFIG_PATH}/PhysiCell_settings.xml")
        root = tree.getroot()
        # Set configurations from model
        for (name, value) in model.get_XML_parameters():
            elem = root.find(f'.//{name}')
            elem.text = str(value)
        if (protocol is not None):
            # Conritubutions from protocol
            for (name, value) in protocol.get_XML_parameters_corrected(sim_params.max_time):
                elem = root.find(f'.//{name}')
                elem.text = str(value)
            #Set dirichlet conditions
            conditions = protocol.get_conditions()
            dirichlet_elem = root.find('.//Dirichlet_options')
            for (name, value) in conditions:
                boundary = dirichlet_elem.find(f"./boundary_value[@ID='{name}']")
                boundary.text = str(value)
            root.find('.//number_of_cells').text = str(len(initial_position_cells))
            tree.write(f"{LocalPhysiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)
        #Set the physiboss simulation parameters
        # Update domain size (assume square domain centered at 0)
        half_size = int(sim_params.domain_size)
        root.find('.//x_min').text = str(-half_size)
        root.find('.//x_max').text = str(half_size)
        root.find('.//y_min').text = str(-half_size)
        root.find('.//y_max').text = str(half_size)
        # Update max_time
        root.find('.//max_time').text = str(int(sim_params.max_time))
        # Update time steps
        root.find('.//dt_diffusion').text = str(sim_params.dt_diffusion)
        root.find('.//dt_mechanics').text = str(sim_params.dt_mechanics)
        root.find('.//dt_phenotype').text = str(sim_params.dt_phenotype)
        # Update number of threads
        root.find('.//omp_num_threads').text = str(int(sim_params.num_threads))
        # Update diffusion coefficient
        root.find('.//diffusion_coefficient').text = str(sim_params.diffusion_coefficient)
        # Update motility speed
        root.find('.//motility/speed').text = str(sim_params.speed)
        # Update intracellular_dt
        root.find('.//intracellular_dt').text = str(int(sim_params.intracellular_dt))
        tree.write(f"{LocalPhysiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)
        # Clean up local job directory
        run_command(f"make data-cleanup", path=LocalPhysiboss.PHYSICELL_PATH)
        # Run the simulation
        run_command(f"./{LocalPhysiboss.BIN_NAME}", path=LocalPhysiboss.PHYSICELL_PATH)
        return os.path.join(LocalPhysiboss.PHYSICELL_PATH, "output")

class RemotePhysiboss:
    BOOLEAN_MODEL_POOL = "../protocols/v1/pool"
    PHYSIBOSS_PATH = f"../physiboss/PhysiCell/"
    CONFIG_PATH = os.path.join(PHYSIBOSS_PATH, "config")
    NETWORK_PATH = os.path.join(CONFIG_PATH, "simple_tnf", "boolean_network")
    BIN_NAME = "project"
    BOOLEAN_NAME = "cellfate"
    REMOTE_HPC_RESULTS_PATH = "masera/results"
    REMOTE_HPC_FAILED_PATH = "masera/failed_jobs"
    HPC_TEMP_PATH = "/home/rsmeriglio/masera/jobs"
    HPC_LOGIN = "rsmeriglio@hpc-legionlogin.polito.it"

    def get_job_list():
        try:
            # Execute SSH command
            result = subprocess.run(
                ["ssh", RemotePhysiboss.HPC_LOGIN, "ls", "-1", RemotePhysiboss.REMOTE_HPC_RESULTS_PATH],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse output into list of filenames
            filenames = result.stdout.strip().split('\n')
            
            # Filter out empty strings if any
            filenames = [f for f in filenames if f.strip()]
            return set(filenames)
        
        except subprocess.CalledProcessError as e:
            print(f"SSH command (success) failed with return code {e.returncode}")
            print(f"Error: {e.stderr}")
            return set()
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
        
    def get_failed_job_list():
        try:
            # Execute SSH command
            result = subprocess.run(
                ["ssh", RemotePhysiboss.HPC_LOGIN, "ls", "-1", RemotePhysiboss.REMOTE_HPC_FAILED_PATH],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse output into list of filenames
            filenames = result.stdout.strip().split('\n')
            
            # Filter out empty strings if any
            filenames = [f for f in filenames if f.strip()]
            return set(filenames)
        
        except subprocess.CalledProcessError as e:
            print(f"SSH command (failed job list) failed with return code {e.returncode}")
            print(f"Error: {e.stderr}")
            return set()
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    def run_remote(model: ModelParameters, protocol: Protocols, 
    job_name: str, sim_params: SimulationParameters, hpc_script_name: str):
        if (protocol is not None):
            protocol.test()

        #Remove old boolean files
        run_command("rm -rf "+RemotePhysiboss.NETWORK_PATH)
        run_command(f"mkdir -p {RemotePhysiboss.NETWORK_PATH}")

        #Set new ones
        base_path = f"{RemotePhysiboss.BOOLEAN_MODEL_POOL}/{model.boolean_family}/{model.boolean_model}"
        cfg_file = f"{base_path}.cfg"
        bnd_file = f"{base_path}.bnd"
        run_command(f"cp {cfg_file} {RemotePhysiboss.NETWORK_PATH}/{RemotePhysiboss.BOOLEAN_NAME}.cfg")
        run_command(f"cp {bnd_file} {RemotePhysiboss.NETWORK_PATH}/{RemotePhysiboss.BOOLEAN_NAME}.bnd")
        for ext in ['cfg', 'bnd']:
            file_path = f"{RemotePhysiboss.NETWORK_PATH}/{RemotePhysiboss.BOOLEAN_NAME}.{ext}"
            # Booleans were built for a different version of physiboss with 2 different nodes names.
            with open(file_path, 'r') as f:
                content = f.read()
            content = content.replace("TNF", "TNFOLD")
            content = content.replace("input_sub", "TNF")
            with open(file_path, 'w') as f:
                f.write(content)

        #Set initial positions
        initial_position_cells = protocol.initial_positions.get_cells()
        if (protocol is not None):
            cells_path = f"{RemotePhysiboss.CONFIG_PATH}/simple_tnf/cells.csv"
            with open(cells_path, 'w') as f:
                f.write("x,y,z,type\n")
                for cell in initial_position_cells:
                    f.write(f"{cell[0]},{cell[1]},{cell[2]},{cell[3]}\n")

        #Update the XML configuration file
        tree = ET.parse(f"{RemotePhysiboss.CONFIG_PATH}/PhysiCell_settings.xml")
        root = tree.getroot()
        # Set configurations from model
        for (name, value) in model.get_XML_parameters():
            elem = root.find(f'.//{name}')
            elem.text = str(value)
        if (protocol is not None):
            # Conritubutions from protocol
            for (name, value) in protocol.get_XML_parameters_corrected(sim_params.max_time):
                elem = root.find(f'.//{name}')
                elem.text = str(value)
            #Set dirichlet conditions
            conditions = protocol.get_conditions()
            dirichlet_elem = root.find('.//Dirichlet_options')
            for (name, value) in conditions:
                boundary = dirichlet_elem.find(f"./boundary_value[@ID='{name}']")
                boundary.text = str(value)
            root.find('.//number_of_cells').text = str(len(initial_position_cells))
            tree.write(f"{RemotePhysiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)
        #Set the physiboss simulation parameters
        # Update domain size (assume square domain centered at 0)
        half_size = int(sim_params.domain_size)
        root.find('.//x_min').text = str(-half_size)
        root.find('.//x_max').text = str(half_size)
        root.find('.//y_min').text = str(-half_size)
        root.find('.//y_max').text = str(half_size)
        # Update max_time
        root.find('.//max_time').text = str(int(sim_params.max_time))
        # Update time steps
        root.find('.//dt_diffusion').text = str(sim_params.dt_diffusion)
        root.find('.//dt_mechanics').text = str(sim_params.dt_mechanics)
        root.find('.//dt_phenotype').text = str(sim_params.dt_phenotype)
        # Update number of threads
        root.find('.//omp_num_threads').text = str(int(sim_params.num_threads))
        # Update diffusion coefficient
        root.find('.//diffusion_coefficient').text = str(sim_params.diffusion_coefficient)
        # Update motility speed
        root.find('.//motility/speed').text = str(sim_params.speed)
        # Update intracellular_dt
        root.find('.//intracellular_dt').text = str(int(sim_params.intracellular_dt))
        tree.write(f"{RemotePhysiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)

        # Prepare the job directory that will be sent to the HPC server
        run_command(f"mkdir {job_name}")
        run_command(f"cp -r {RemotePhysiboss.CONFIG_PATH} {job_name}/")
        run_command(f"mkdir {job_name}/output")

        # Send the job to the HPC server and run it
        run_command(f"scp -r {job_name} ssh {RemotePhysiboss.HPC_LOGIN}:{RemotePhysiboss.HPC_TEMP_PATH}")
        run_command(f"ssh {RemotePhysiboss.HPC_LOGIN} sbatch {hpc_script_name} {job_name}")

        # Clean up local job directory
        run_command(f"rm -rf {job_name}")

    def run_remote_with_lock(model: ModelParameters, protocol: Protocols, 
    job_name: str, sim_params: SimulationParameters, hpc_script_name: str, LOCK):
        
        with LOCK:
            #Remove old boolean files
            run_command("rm -rf "+RemotePhysiboss.NETWORK_PATH)
            run_command(f"mkdir -p {RemotePhysiboss.NETWORK_PATH}")

            #Set new ones
            base_path = f"{RemotePhysiboss.BOOLEAN_MODEL_POOL}/{model.boolean_family}/{model.boolean_model}"
            cfg_file = f"{base_path}.cfg"
            bnd_file = f"{base_path}.bnd"
            run_command(f"cp {cfg_file} {RemotePhysiboss.NETWORK_PATH}/{RemotePhysiboss.BOOLEAN_NAME}.cfg")
            run_command(f"cp {bnd_file} {RemotePhysiboss.NETWORK_PATH}/{RemotePhysiboss.BOOLEAN_NAME}.bnd")
            for ext in ['cfg', 'bnd']:
                file_path = f"{RemotePhysiboss.NETWORK_PATH}/{RemotePhysiboss.BOOLEAN_NAME}.{ext}"
                # Booleans were built for a different version of physiboss with 2 different nodes names.
                with open(file_path, 'r') as f:
                    content = f.read()
                content = content.replace("TNF", "TNFOLD")
                content = content.replace("input_sub", "TNF")
                with open(file_path, 'w') as f:
                    f.write(content)

            #Set initial positions
            initial_position_cells = protocol.initial_positions.get_cells()
            if (protocol is not None):
                cells_path = f"{RemotePhysiboss.CONFIG_PATH}/simple_tnf/cells.csv"
                with open(cells_path, 'w') as f:
                    f.write("x,y,z,type\n")
                    for cell in initial_position_cells:
                        f.write(f"{cell[0]},{cell[1]},{cell[2]},{cell[3]}\n")

            #Update the XML configuration file
            tree = ET.parse(f"{RemotePhysiboss.CONFIG_PATH}/PhysiCell_settings.xml")
            root = tree.getroot()
            # Set configurations from model
            for (name, value) in model.get_XML_parameters():
                elem = root.find(f'.//{name}')
                elem.text = str(value)
            if (protocol is not None):
                # Conritubutions from protocol
                for (name, value) in protocol.get_XML_parameters_corrected(sim_params.max_time):
                    elem = root.find(f'.//{name}')
                    elem.text = str(value)
                #Set dirichlet conditions
                conditions = protocol.get_conditions()
                dirichlet_elem = root.find('.//Dirichlet_options')
                for (name, value) in conditions:
                    boundary = dirichlet_elem.find(f"./boundary_value[@ID='{name}']")
                    boundary.text = str(value)
                root.find('.//number_of_cells').text = str(len(initial_position_cells))
                tree.write(f"{RemotePhysiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)
            #Set the physiboss simulation parameters
            # Update domain size (assume square domain centered at 0)
            half_size = int(sim_params.domain_size)
            root.find('.//x_min').text = str(-half_size)
            root.find('.//x_max').text = str(half_size)
            root.find('.//y_min').text = str(-half_size)
            root.find('.//y_max').text = str(half_size)
            # Update max_time
            root.find('.//max_time').text = str(int(sim_params.max_time))
            # Update time steps
            root.find('.//dt_diffusion').text = str(sim_params.dt_diffusion)
            root.find('.//dt_mechanics').text = str(sim_params.dt_mechanics)
            root.find('.//dt_phenotype').text = str(sim_params.dt_phenotype)
            # Update number of threads
            root.find('.//omp_num_threads').text = str(int(sim_params.num_threads))
            # Update diffusion coefficient
            root.find('.//diffusion_coefficient').text = str(sim_params.diffusion_coefficient)
            # Update motility speed
            root.find('.//motility/speed').text = str(sim_params.speed)
            # Update intracellular_dt
            root.find('.//intracellular_dt').text = str(int(sim_params.intracellular_dt))
            tree.write(f"{RemotePhysiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)

            # Prepare the job directory that will be sent to the HPC server
            run_command(f"mkdir {job_name}")
            run_command(f"cp -r {RemotePhysiboss.CONFIG_PATH} {job_name}/")
            run_command(f"mkdir {job_name}/output")

        # Send the job to the HPC server and run it
        run_command(f"echo $PWD && scp -r {job_name} {RemotePhysiboss.HPC_LOGIN}:{RemotePhysiboss.HPC_TEMP_PATH}")
        run_command(f"ssh {RemotePhysiboss.HPC_LOGIN} sbatch {hpc_script_name} {job_name}")

        # Clean up local job directory
        run_command(f"rm -rf {job_name}")