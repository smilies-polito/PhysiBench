# physiboss.py
import os
import time
from dataclasses import dataclass
import subprocess
import xml.etree.ElementTree as ET
from typing import Tuple, List

from initial_positions import InitialPosition

PRJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ssh/scp options to avoid interactive prompts and host key issues
SSH_OPTS = "-o BatchMode=yes -o StrictHostKeyChecking=accept-new"

def _ssh(cmd: str, remote_user: str, remote_host: str) -> int:
    """Run a command on the remote HPC via ssh with safe options."""
    return os.system(f"ssh {SSH_OPTS} {remote_user}@{remote_host} '{cmd}'")

def _scp(local: str, remote_subdir: str, remote_user: str, remote_host: str, remote_base: str) -> int:
    """Copy a local path to HPC REMOTE_BASE/remote_subdir via scp with safe options."""
    return os.system(
        f"scp -r {SSH_OPTS} {local} {remote_user}@{remote_host}:{remote_base}/{remote_subdir}"
    )

@dataclass
class ModelParameters:
    boolean_family: str
    boolean_model: str
    def test(self):
        bnd = f"{PRJ_ROOT}/protocols/v1/pool/{self.boolean_family}/{self.boolean_model}.bnd"
        cfg = f"{PRJ_ROOT}/protocols/v1/pool/{self.boolean_family}/{self.boolean_model}.cfg"
        if not (os.path.exists(bnd) and os.path.exists(cfg)):
            raise ValueError(f"Model {self.boolean_family}/{self.boolean_model} does not exist.")

    def get_XML_parameters(self) -> List[Tuple[str, float]]:
        # se servono parametri globali del modello, aggiungili qui
        return []

@dataclass
class Protocols:
    # *** ASSOLUTI, NIENTE NORMALIZZAZIONE ***
    treatment_duration: float  # minuti
    treatment_period: float    # minuti
    xmin: float                # 0..10
    xmax: float                # 0..10
    ymin: float                # 0..10
    ymax: float                # 0..10
    initial_positions: InitialPosition

    def get_XML_parameters(self) -> List[Tuple[str, float]]:
        # scrivi i valori direttamente (assoluti)
        return [
            ("treatment_duration", self.treatment_duration),
            ("treatment_period", self.treatment_period),
        ]

    def get_conditions(self) -> List[Tuple[str, float]]:
        return [
            ("xmin", self.xmin),
            ("xmax", self.xmax),
            ("ymin", self.ymin),
            ("ymax", self.ymax),
        ]

class Physiboss:
    PHYSIBOSS_PATH = f"{PRJ_ROOT}/bin/PhysiCell/"
    CONFIG_PATH = os.path.join(PHYSIBOSS_PATH, "config")
    NETWORK_PATH = os.path.join(CONFIG_PATH, "simple_tnf", "boolean_network")
    BIN_NAME = "project"
    BOOLEAN_NAME = "cellfate"

    @staticmethod
    def _prepare_boolean_files(model: ModelParameters) -> None:
        os.system("rm -rf " + Physiboss.NETWORK_PATH)
        os.system(f"mkdir -p {Physiboss.NETWORK_PATH}")

        base_path = f"{PRJ_ROOT}/protocols/v1/pool/{model.boolean_family}/{model.boolean_model}"
        cfg_file = f"{base_path}.cfg"
        bnd_file = f"{base_path}.bnd"
        os.system(f"cp {cfg_file} {Physiboss.NETWORK_PATH}/{Physiboss.BOOLEAN_NAME}.cfg")
        os.system(f"cp {bnd_file} {Physiboss.NETWORK_PATH}/{Physiboss.BOOLEAN_NAME}.bnd")
        # mapping richiesto dal tuo progetto
        for ext in ['cfg', 'bnd']:
            file_path = f"{Physiboss.NETWORK_PATH}/{Physiboss.BOOLEAN_NAME}.{ext}"
            with open(file_path, 'r') as f:
                content = f.read()
            content = content.replace("TNF", "TNFOLD")
            content = content.replace("input_sub", "TNF")
            with open(file_path, 'w') as f:
                f.write(content)

    @staticmethod
    def _write_initial_positions(protocol: Protocols) -> int:
        initial_position_cells = protocol.initial_positions.get_cells()
        cells_path = f"{Physiboss.CONFIG_PATH}/simple_tnf/cells.csv"
        os.makedirs(os.path.dirname(cells_path), exist_ok=True)
        with open(cells_path, 'w') as f:
            f.write("x,y,z,type\n")
            for cell in initial_position_cells:
                f.write(f"{cell[0]},{cell[1]},{cell[2]},{cell[3]}\n")
        return len(initial_position_cells)

    @staticmethod
    def _prepare_local_config(model: ModelParameters, protocol: Protocols, job_name: str, sim_params) -> None:
        """
        Prepara la cartella locale del job:
        - aggiorna boolean network
        - scrive positions
        - aggiorna XML con parametri del modello/protocollo
        - setta dominio, max_time, dts, omp, diffusion, motility, intracellular_dt
        - setta save_time (interval)
        - copia config/ nel job folder
        """

        # Boolean network
        Physiboss._prepare_boolean_files(model)

        # Initial positions
        n_cells = Physiboss._write_initial_positions(protocol)

        # Update the XML configuration file
        tree = ET.parse(f"{Physiboss.CONFIG_PATH}/PhysiCell_settings.xml")
        root = tree.getroot()

        # model-level params (se ce ne sono)
        for (name, value) in model.get_XML_parameters():
            elem = root.find(f'.//{name}')
            if elem is not None:
                elem.text = str(value)

        # protocol-level params ASSOLUTI
        if protocol is not None:
            for (name, value) in protocol.get_XML_parameters():
                elem = root.find(f'.//{name}')
                if elem is not None:
                    elem.text = str(value)

            # Dirichlet conditions
            dirichlet_elem = root.find('.//Dirichlet_options')
            if dirichlet_elem is not None:
                for (name, value) in protocol.get_conditions():
                    boundary = dirichlet_elem.find(f"./boundary_value[@ID='{name}']")
                    if boundary is not None:
                        boundary.text = str(value)

        # dominio e run-time settings
        half_size = int(sim_params.domain_size)
        x_min = root.find('.//x_min');                 x_min.text = str(-half_size)
        x_max = root.find('.//x_max');                 x_max.text = str(half_size)
        y_min = root.find('.//y_min');                 y_min.text = str(-half_size)
        y_max = root.find('.//y_max');                 y_max.text = str(half_size)
        max_time = root.find('.//max_time');           max_time.text = str(int(sim_params.max_time))
        dt_diffusion = root.find('.//dt_diffusion');   dt_diffusion.text = str(sim_params.dt_diffusion)
        dt_mechanics = root.find('.//dt_mechanics');   dt_mechanics.text = str(sim_params.dt_mechanics)
        dt_phenotype = root.find('.//dt_phenotype');   dt_phenotype.text = str(sim_params.dt_phenotype)
        omp = root.find('.//omp_num_threads');         omp.text = str(int(sim_params.num_threads))
        diff = root.find('.//diffusion_coefficient');  diff.text = str(sim_params.diffusion_coefficient)
        mot = root.find('.//motility/speed');          mot.text = str(sim_params.speed)
        ic  = root.find('.//intracellular_dt');        ic.text = str(int(sim_params.intracellular_dt))
        nc  = root.find('.//number_of_cells');         nc.text = str(n_cells)

        # save interval
        interval_node = root.find('.//save/full_data/interval')
        if interval_node is None:
            interval_node = root.find('.//full_data/interval')
        if interval_node is not None and getattr(sim_params, "save_time", None) is not None:
            interval_node.text = str(sim_params.save_time)

        # scrivi XML
        tree.write(f"{Physiboss.CONFIG_PATH}/PhysiCell_settings.xml", encoding='utf-8', xml_declaration=True)

        # prepara cartella job
        os.system(f"rm -rf {job_name}")
        os.system(f"mkdir {job_name}")
        os.system(f"cp -r {Physiboss.CONFIG_PATH} {job_name}/")
        os.system(f"mkdir {job_name}/output")

    @staticmethod
    def run_remote_wt_settings(model: ModelParameters, protocol: Protocols, job_name: str, sim_params,
                               remote_user: str, remote_host: str, remote_base: str, run_script: str):
        """
        Prepara config in locale (incluso save_time), copia al cluster e sottomette il job.
        """
        Physiboss._prepare_local_config(model, protocol, job_name, sim_params)

        # Retry until the job folder is copied successfully.
        while True:
            scp_rc = _scp(job_name, "jobs", remote_user, remote_host, remote_base)
            if scp_rc == 0:
                break
            print(f"⚠️ scp failed for {job_name} (exit={scp_rc}). Retry in 60s...")
            time.sleep(60)

        # Retry until sbatch submission succeeds.
        while True:
            ssh_rc = _ssh(f"sbatch {run_script} {job_name}", remote_user, remote_host)
            if ssh_rc == 0:
                break
            print(f"⚠️ sbatch failed for {job_name} (exit={ssh_rc}). Retry in 60s...")
            time.sleep(60)

        os.system(f"rm -rf {job_name}")

    # --- utility per l’esecuzione locale (opzionale) ---
    @staticmethod
    def run(model: ModelParameters, protocol: Protocols):
        """
        Run the Physiboss simulation locally (non-HPC).
        """
        Physiboss._prepare_local_config(model, protocol, "local_job", type("S", (), {
            "domain_size": 200,
            "max_time": 5000,
            "dt_diffusion": 0.01,
            "dt_mechanics": 0.1,
            "dt_phenotype": 0.1,
            "num_threads": 4,
            "diffusion_coefficient": 1e-5,
            "speed": 1.0,
            "intracellular_dt": 1,
            "save_time": 30,
        })())

        os.chdir(Physiboss.PHYSIBOSS_PATH)
        cleanup = ["make", 'data-cleanup']
        subprocess.run(cleanup, check=True, stdout=subprocess.DEVNULL)
        execute_command = ["./" + Physiboss.BIN_NAME]
        subprocess.run(execute_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        output_folder = f"{Physiboss.PHYSIBOSS_PATH}/output"
        return os.path.abspath(output_folder)
