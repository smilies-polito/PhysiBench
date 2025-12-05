import os
from dataclasses import dataclass
import random
from initial_positions import InitialPosition

#############################################################
#    ModelParameters:
#        - Parameters that define a model: boolean family and model
#    Usage: 
#        ModelParameters(
#            boolean_family="name_of_boolean_family",
#            boolean_model="name_of_boolean_model"
#        )
#
#    Protocols:
#        - Individual protocols for the simulation: treatment duration and period, initial positions, domain size
#    Usage: 
#        Protocols(
#            treatment_duration=0.5, # 0-1
#            treatment_period=0.1, # 0-0.5
#            xmin=0, # 0-10
#            xmax=10, # 0-10
#            ymin=0, # 0-10
#            ymax=10, # 0-10
#            initial_positions=InitialPosition(...) # See InitialPosition class in initial_positions.py
#        )
#
#    SimulationParameters:
#        - Settings for physiboss.
#    Usage:
#        SimulationParameters.get_defaults() # to get default parameters we are using.
#############################################################




@dataclass
class ModelParameters:
    boolean_family: str
    boolean_model: str 

    def get_XML_parameters(self):
        return []

@dataclass
class Protocols:
    SIMULATION_MAX_TIME = 5000

    treatment_duration: float #0-1
    treatment_period: float #0-0.5
    xmin: float #0-10
    xmax: float #0-10
    ymin: float #0-10
    ymax: float #0-10
    initial_positions: InitialPosition


    def test(self):
        if not (0 <= self.treatment_duration <= 1):
            raise ValueError("treatment_duration must be between 0 and 1")
        if not (0 <= self.treatment_period <= 0.5):
            raise ValueError("treatment_period must be between 0 and 0.5")
        if not (0 <= self.xmin <= 10):
            raise ValueError("xmin must be between 0 and 10")
        if not (0 <= self.xmax <= 10):
            raise ValueError("xmax must be between 0 and 10")
        if not (0 <= self.ymin <= 10):
            raise ValueError("ymin must be between 0 and 10")
        if not (0 <= self.ymax <= 10):
            raise ValueError("ymax must be between 0 and 10")
        if self.xmax - self.xmin > 10:
            raise ValueError("xmax - xmin must be less than or equal to 10")
        if self.ymax - self.ymin > 10:
            raise ValueError("ymax - ymin must be less than or equal to 10")
    def get_XML_parameters(self):
        return [
            ("treatment_duration", (Protocols.SIMULATION_MAX_TIME * self.treatment_period) * self.treatment_duration),
            ("treatment_period", Protocols.SIMULATION_MAX_TIME * self.treatment_period),
        ]
    def get_XML_parameters_corrected(self, MAX_TIME):
        return [
            ("treatment_duration", (MAX_TIME * self.treatment_period) * self.treatment_duration),
            ("treatment_period", MAX_TIME * self.treatment_period),
        ]
    def get_conditions(self):
        return [
            ("xmin", self.xmin),
            ("xmax", self.xmax),
            ("ymin", self.ymin),
            ("ymax", self.ymax),
        ]

@dataclass 
class SimulationParameters:
    domain_size: float  # 200-500
    max_time: float     # 2000-5000
    dt_diffusion: float # 0.1-0.4
    dt_mechanics: float # 0.1-0.4
    dt_phenotype: float # 6
    num_threads: int    # 1-4
    diffusion_coefficient: float # 800-1600
    speed: float        # 1-3
    intracellular_dt: int = 1000 #500 - 1800

    def get_defaults():
        return SimulationParameters(
            domain_size=206,
            max_time=1700,
            dt_diffusion=0.256,
            dt_mechanics=0.152,
            dt_phenotype=5.718,
            num_threads=3,
            diffusion_coefficient=1070.0,
            speed=3.3,
            intracellular_dt=518
        )

    def to_hash(self):
        def to_two_decimals(x):
            return f"{x:.1f}"
        def to_int(x):
            return f"{int(x)}"
        return "_".join([
            to_two_decimals(self.domain_size),
            to_int(self.max_time),
            to_two_decimals(self.dt_diffusion),
            to_two_decimals(self.dt_mechanics),
            to_two_decimals(self.dt_phenotype),
            to_int(self.num_threads),
            to_int(self.diffusion_coefficient),
            to_two_decimals(self.speed)
        ])