import os
from dataclasses import dataclass
import subprocess
import xml.etree.ElementTree as ET
from simulation_model_protocol import ModelParameters, Protocols, SimulationParameters
import subprocess
import traceback
import time
from contextlib import nullcontext

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
SSH_MULTIPLEX_ARGS = [
    "-o", "ControlMaster=auto ",
    "-o", " ControlPath=/tmp/ssh-%r@%h:%p ",
    "-o", " ControlPersist=10m ",
    "-o", " ServerAliveInterval=60",
]
SSH_MULTIPLEX_ARGS_STRINGIFIED = " ".join(SSH_MULTIPLEX_ARGS)


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

    PHYSICELL_PATH = "../bin/physiboss/PhysiCell/"
    CONFIG_PATH = os.path.join(PHYSICELL_PATH, "config")
    NETWORK_PATH = os.path.join(CONFIG_PATH, "simple_tnf", "boolean_network")
    OUTPUT_DIR = os.path.join(PHYSICELL_PATH, "output")
    
    if is_singularity():
        NETWORK_PATH = "/virtualconfig/simple_tnf/boolean_network"
        CONFIG_PATH = "/virtualconfig"
        PHYSICELL_PATH = "/bin/PhysiCell"
        OUTPUT_DIR = "/virtualoutput"
    
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
        # Update save interval
        root.find('.//save/full_data/interval').text = str(sim_params.save_interval)
        tree.write(f"{LocalPhysiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)
        # Clean up local job directory
        run_command(f"rm -rf output/*", path=LocalPhysiboss.PHYSICELL_PATH)
        # Run the simulation
        run_command(f"./{LocalPhysiboss.BIN_NAME}", path=LocalPhysiboss.PHYSICELL_PATH)
        return os.path.join(LocalPhysiboss.PHYSICELL_PATH, "output")

class RemotePhysiboss:
    def __init__(
        self,
        boolean_model_pool: str,
        remote_hpc_results_path: str,
        remote_hpc_failed_path: str,
        hpc_temp_path: str,
        hpc_login: str,
        hpc_script_name: str
    ):
        self.BOOLEAN_MODEL_POOL = boolean_model_pool
        self.PHYSIBOSS_PATH = LocalPhysiboss.PHYSICELL_PATH
        self.CONFIG_PATH = LocalPhysiboss.CONFIG_PATH
        self.NETWORK_PATH = LocalPhysiboss.NETWORK_PATH
        self.BOOLEAN_NAME = LocalPhysiboss.NETWORK_BASE_NAME
        self.REMOTE_HPC_RESULTS_PATH = remote_hpc_results_path
        self.REMOTE_HPC_FAILED_PATH = remote_hpc_failed_path
        self.HPC_TEMP_PATH = hpc_temp_path
        self.HPC_LOGIN = hpc_login
        self.HPC_SCRIPT_NAME = hpc_script_name

    def get_job_list(self):
        try:
            # Execute SSH command
            result = subprocess.run(
                ["ssh"] + SSH_MULTIPLEX_ARGS + [self.HPC_LOGIN, "ls -1", self.REMOTE_HPC_RESULTS_PATH],
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
            print(f"SSH command (get job list) failed with return code {e.returncode}")
            print(f"Error: {e.stderr}")
            return set()
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
        
    def retrieve_all_remote_jobs(self, local_output_path: str, delete_after_retrieval=False):
        try:
            jobs = self.get_job_list()
            print(f"Retrieving {len(jobs)} jobs from the HPC server...")
            system_command = f"scp {SSH_MULTIPLEX_ARGS_STRINGIFIED} -r  {self.HPC_LOGIN}:{self.REMOTE_HPC_RESULTS_PATH}/* {local_output_path}"
            run_command(system_command)
        except Exception as e:
            print("Error retrieving job list from the HPC:", e)
        
    def get_failed_job_list(self):
        try:
            # Execute SSH command
            result = subprocess.run(
                ["ssh", self.HPC_LOGIN, "ls -1", self.REMOTE_HPC_FAILED_PATH],
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

    def run_remote_with_polling(
        self,
        model: ModelParameters,
        protocol: Protocols,
        job_name: str,
        sim_params: SimulationParameters,
        local_output_path: str,
        POLLING_ATTEMPTS: int,
        POLLING_INTERVAL_SECONDS: int,
        PHYSIBOSS_DIR_LOCK=None,
    ):

        try:
            self.run_remote_and_not_fetch(
                model, protocol, job_name, sim_params, PHYSIBOSS_DIR_LOCK
            )
        except Exception as e:
            print("Error submitting job to HPC - ", job_name, ":", e)
            traceback.print_exc()
            return None
        try:
            # Polling to retrieve the result
            for _ in range(POLLING_ATTEMPTS):
                time.sleep(POLLING_INTERVAL_SECONDS)
                jobs = self.get_job_list()

                # Check if job completed successfully
                if job_name in jobs:
                    try:
                        remote_hpc_job = os.path.join(self.REMOTE_HPC_RESULTS_PATH, job_name, "output")
                        local_job = os.path.join(local_output_path, job_name)
                        system_command = f"scp {SSH_MULTIPLEX_ARGS_STRINGIFIED} -r  {self.HPC_LOGIN}:{remote_hpc_job} {local_job}"
                        run_command(system_command)
                        return local_job

                    except Exception as e:
                        print("Error retrieving job from the HPC - ", job_name, ":", e)
                        return None

                    finally:
                        try:
                            run_command(f"ssh {self.HPC_LOGIN} {SSH_MULTIPLEX_ARGS_STRINGIFIED} rm -rf {os.path.join(self.REMOTE_HPC_RESULTS_PATH, job_name)}")
                        except Exception as e:
                            print("Cannot clean up job files for", job_name)

                # Check if job failed
                failed_jobs = self.get_failed_job_list()
                if job_name in failed_jobs:
                    print("Error running the job from the HPC - ", job_name, "Job has been left in failed_jobs.")
                    return None

            print(f"Job {job_name} did not complete within the polling time. Giving up and freeing the subprocess.")
            return None
        except Exception as e:
            print("Error submitting job", job_name, ":", e)
            traceback.print_exc()
            return None
        

    def run_remote_and_not_fetch(
        self,
        model: ModelParameters,
        protocol: Protocols,
        job_name: str,
        sim_params: SimulationParameters,
        LOCK,
    ):
        
        safe_lock = LOCK or nullcontext()

        with safe_lock:
            #Remove old boolean files
            run_command("rm -rf " + self.NETWORK_PATH)
            run_command(f"mkdir -p {self.NETWORK_PATH}")

            #Set new ones
            base_path = f"{self.BOOLEAN_MODEL_POOL}/{model.boolean_family}/{model.boolean_model}"
            cfg_file = f"{base_path}.cfg"
            bnd_file = f"{base_path}.bnd"
            run_command(f"cp {cfg_file} {self.NETWORK_PATH}/{self.BOOLEAN_NAME}.cfg")
            run_command(f"cp {bnd_file} {self.NETWORK_PATH}/{self.BOOLEAN_NAME}.bnd")
            for ext in ['cfg', 'bnd']:
                file_path = f"{self.NETWORK_PATH}/{self.BOOLEAN_NAME}.{ext}"
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
                cells_path = f"{self.CONFIG_PATH}/simple_tnf/cells.csv"
                with open(cells_path, 'w') as f:
                    f.write("x,y,z,type\n")
                    for cell in initial_position_cells:
                        f.write(f"{cell[0]},{cell[1]},{cell[2]},{cell[3]}\n")

            #Update the XML configuration file
            tree = ET.parse(f"{self.CONFIG_PATH}/PhysiCell_settings.xml")
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
                tree.write(f"{self.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)
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
            # Update save interval
            root.find('.//save/full_data/interval').text = str(sim_params.save_interval)
            tree.write(f"{self.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)

            # Prepare the job directory that will be sent to the HPC server
            run_command(f"mkdir {job_name}")
            run_command(f"cp -r {self.CONFIG_PATH} {job_name}/")
            if os.path.exists(f"{job_name}/virtualconfig"):
                run_command(f"mv {job_name}/virtualconfig {job_name}/config")
            run_command(f"mkdir {job_name}/output")

        # Send the job to the HPC server and run it
        run_command(f"echo $PWD && scp {SSH_MULTIPLEX_ARGS_STRINGIFIED} -r {job_name} {self.HPC_LOGIN}:{self.HPC_TEMP_PATH}")
        run_command(f"ssh {self.HPC_LOGIN} {SSH_MULTIPLEX_ARGS_STRINGIFIED} sbatch {self.HPC_SCRIPT_NAME} {job_name}")

        # Clean up local job directory
        run_command(f"rm -rf {job_name}")