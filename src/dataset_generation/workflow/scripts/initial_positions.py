import csv
from dataclasses import dataclass
import math
import random
from typing import List, Tuple
import sys


#############################################################
#    Initial Position:
#        - Abstract the initial position of cells into PhysiBoss.
#    
#    Usage: 
#        InitialPosition(
#            type="circle" or "square",
#            center=(x, y),
#            density=0.1,
#            cell_type=0, # Sempre 0, non abbiamo mai implementato multipli booleani
#            mode="sparse" or "contour" # dense non usato
#            length=50.0 # raggio del cerchio o lato del quadrato
#        )
#############################################################




Cell = Tuple[float, float, float, int]  # x, y, z, cell_type_id
# Default spacing for dense and contour modes (based on volume of 1000 u^3 in PhysiCell settings)
SPACING_DEFAULT = 16.82
X_MAX = 100
X_MIN = -100
Y_MAX = 100
Y_MIN = -100

@dataclass
class InitialPosition:
    type: str #circle or square
    center: Tuple[float, float] #Diagonale superiore sinistra
    density: float = 0.1
    cell_type: str = "default" #Se vogliamo usare + booleani 
    mode: str = "sparse" #dense, sparse, contour
    length: float = 0.0 #Lato del quadrato o raggio del cerchio

    def get_random():
        # Generate a random length or radius
        length = random.uniform(50, (X_MAX - X_MIN) / 2.6)
        # Generate a random center within the domain boundaries
        cx = random.uniform(X_MIN+(length/2), X_MAX-(length/2))
        cy = random.uniform(Y_MIN+(length/2), Y_MAX-(length/2))
        
        # Generate a random density
        density = random.uniform(0, 0.8)
        cell_type = "default"
        mode = random.choice(["sparse", "contour"])
        type = random.choice(["circle", "square"])
        return InitialPosition(
            type=type,
            center=(cx, cy),
            density=density,
            cell_type=cell_type,
            mode=mode,
            length=length
        )
    def get_cells(self) -> List[Cell]:
        if self.type == "circle":
            return fill_circle(
                center=self.center,
                radius=self.length,
                density=self.density,
                cell_type=self.cell_type,
                mode=self.mode
            )
        elif self.type == "square":
            return fill_square(
                center=self.center,
                half=self.length,
                density=self.density,
                cell_type=self.cell_type,
                mode=self.mode
            )
        else:
            raise ValueError("Type must be 'circle' or 'square'.")


def fill_circle(
    center: Tuple[float, float],
    radius: float,
    spacing: float = SPACING_DEFAULT,
    density: float = 0.1,
    cell_type: str = "default",
    mode: str = "sparse"
) -> List[Cell]:
    
    if density < 0 or density > 1:
        raise ValueError("Density must be between 0 and 1.")
    
    cx, cy = center
     
    # affirming domain boundaries
    if cx <= X_MIN or cx >= X_MAX or cy<=Y_MIN or cy>=Y_MAX:
        raise ValueError(f"Center must be within domain boundaries: center: {center} X_MIN={X_MIN};X_MAX={X_MAX};Y_MIN={Y_MIN};Y_MAX={Y_MAX};Z_MIN={Z_MIN};Z_MAX={Z_MAX}")

    cells: List[Cell] = []
    possible_cells: List[Cell] = []

    x_min, x_max = cx - radius, cx + radius
    y_min, y_max = cy - radius, cy + radius
    x = x_min
    
    
    
    # affirming domain boundaries
    if x_min <= X_MIN:
        x_min=X_MIN
    if x_max >= X_MAX:
        x_max=X_MAX
    if y_min <= Y_MIN:
        y_min=Y_MIN
    if y_max >= Y_MAX:
        y_max=Y_MAX

    x = x_min
    while x <= x_max:
        y = y_min
        while y <= y_max:
            if (x - cx)**2 + (y - cy)**2 <= radius**2:
                possible_cells.append((x, y, 0.0, cell_type))
            y += spacing
        x += spacing

    max_n_cells = len(possible_cells)

    if mode == "sparse":
        
        if density == 1:
            cells = possible_cells
        else:
            n_cells = int(density * max_n_cells)
            cells = random.sample(possible_cells, n_cells)
                    
    elif mode == "contour":
        for cell in possible_cells:
            x, y, _, _ = cell
            distance = math.sqrt((x - cx)**2 + (y - cy)**2)
            if radius - spacing <= distance <= radius:
                cells.append(cell)

    
    else:
        raise ValueError("Mode must be 'dense', 'sparse', or 'contour'. " + mode)


    return cells


def fill_square(
    center: Tuple[float, float],
    half: float,
    spacing: float = SPACING_DEFAULT,
    density: float = 0.1,
    cell_type: str = "default",
    mode: str = "sparse"
) -> List[Cell]:
    
    if density < 0 or density > 1:
        raise ValueError("Density must be between 0 and 1.")
    

    cx, cy = center
    side = half * 2

    if cx <= X_MIN or cx >= X_MAX or cy<=Y_MIN or cy>=Y_MAX:
        raise ValueError(f"Center must be within domain boundaries: center: {center} X_MIN={X_MIN};X_MAX={X_MAX};Y_MIN={Y_MIN};Y_MAX={Y_MAX};")

    x_min, x_max = cx - half, cx + half
    y_min, y_max = cy - half, cy + half

    possible_cells: List[Cell] = []

    # --- Costruzione della griglia regolare (possible_cells) ---
    x = x_min
    while x <= x_max:
        y = y_min
        while y <= y_max:
            possible_cells.append((x, y, 0.0, cell_type))
            y += spacing
        x += spacing

    max_n_cells = len(possible_cells)

    cells: List[Cell] = []

    # --- Riempimento in base al mode ---

    if mode == "sparse" or mode == "dense":
        if density == 1:
            cells = possible_cells
        else:
            n_cells = int(density * max_n_cells)
            cells = random.sample(possible_cells, n_cells)

    elif mode == "contour":

        x_min = min(cell[0] for cell in possible_cells)
        x_max = max(cell[0] for cell in possible_cells)
        y_min = min(cell[1] for cell in possible_cells)
        y_max = max(cell[1] for cell in possible_cells)
        for cell in possible_cells:
            x, y, _, _ = cell
            # Se il punto è vicino a uno dei 4 bordi
            if x == x_min or x == x_max or y == y_min or y == y_max:
                cells.append(cell)

    else:
        raise ValueError("Mode must be 'dense', 'sparse', or 'contour'."  + mode)

    return cells