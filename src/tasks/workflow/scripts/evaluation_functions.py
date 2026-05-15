from abc import ABC, abstractmethod

import numpy as np
from enum import Enum
import scipy.io

class EvaluationFunction(ABC):
    @abstractmethod
    def run(_, output_path) -> float:
        pass

class AliveCellsFunction(EvaluationFunction):
    def run(self, output_path) -> float:
        cells = scipy.io.loadmat(output_path)['cells'][7,:]
        return (cells==14).sum()
    

class Apoptotic(EvaluationFunction):
    def run(self, output_path) -> float:
        cells = scipy.io.loadmat(output_path)['cells'][7,:]
        return (cells==100).sum()

### Spatial functions
from scipy import stats


# Helper function
def load_alive_cells(output_path):
    cells = scipy.io.loadmat(output_path)['cells']
    alive_mask = cells[7, :] == 14
    cells = cells[(1, 2), :][:, alive_mask].reshape(-1, 2)
    return cells


class SpatialEvaluationFunctionType(Enum):
    LINEAR = 1  # num cells outside - Num cells inside  (smaller is always better)
    LINEAR_WT_DISTRIBUTION = 2  # As linear, but penalizes the distribution of cells if not uniform

class CircularEvaluationFunction(EvaluationFunction):
    def __init__(self, center: tuple, radius: float, function_type: SpatialEvaluationFunctionType = SpatialEvaluationFunctionType.LINEAR):
        self.center = center
        self.radius = radius
        self.function_type = function_type
    
    @staticmethod
    def test_distance_uniformity(squared_distances, radius_squared):
        # Normalize squared distances - should be uniform if points are evenly distributed
        normalized_squared_distances = squared_distances / radius_squared
        # Test against a uniform distribution
        ks_statistic, _ = stats.kstest(normalized_squared_distances, 'uniform')
        if np.isnan(ks_statistic):
            return 0
        return 1 - ks_statistic

    @staticmethod
    def test_angle_uniformity(angles): #Kolmogorov-Smirnov Test
        normalized_angles = (angles + np.pi) / (2 * np.pi)
        ks_statistic, _ = stats.kstest(normalized_angles, 'uniform')
        if (np.isnan(ks_statistic)):
            return 0
        return 1 - ks_statistic

    def run(self, output_path) -> float:
        cells = load_alive_cells(output_path)
        if (len(cells) == 0):
            return 0
        inside = 0
        outside = 0
        if (self.function_type == SpatialEvaluationFunctionType.LINEAR):
            for cell in cells:
                x = cell[0]
                y = cell[1]
                if (x-self.center[0])**2 + (y-self.center[1])**2 > self.radius**2:
                    outside += 1
                else:
                    inside += 1
            return outside - inside
        else:
            distance_from_center = []
            angle = []
            for cell in cells:
                x = cell[0]
                y = cell[1]
                if (x-self.center[0])**2 + (y-self.center[1])**2 > self.radius**2:
                    outside += 1
                else:
                    inside += 1
                    distance_from_center.append((x-self.center[0])**2 + (y-self.center[1])**2)
                    angle.append(np.arctan2(y-self.center[1], x-self.center[0]))
            if (inside == 0):
                return outside
            distance_from_center = np.array(distance_from_center)
            angle = np.array(angle)
            distance_uniformity = CircularEvaluationFunction.test_distance_uniformity(
                np.array(distance_from_center), 
                self.radius**2
            )
            angle_uniformity = CircularEvaluationFunction.test_angle_uniformity(angle)
            score = (distance_uniformity + angle_uniformity) / 2
            return outside - (inside * score)

class SquaredEvaluationFunction(EvaluationFunction):
    def __init__(self, center: tuple, side_length: float, function_type: SpatialEvaluationFunctionType = SpatialEvaluationFunctionType.LINEAR):
        self.center = center
        self.side_length = side_length
        self.half_side = side_length / 2
        self.function_type = function_type

    @staticmethod
    def test_x_uniformity(x_positions, half_side):
        # Normalize x positions to [0,1] range
        normalized_x = (x_positions + half_side) / (2 * half_side)
        # Test against a uniform distribution
        ks_statistic, _ = stats.kstest(normalized_x, 'uniform')
        if np.isnan(ks_statistic):
            return 0
        return 1 - ks_statistic

    @staticmethod
    def test_y_uniformity(y_positions, half_side):
        # Normalize y positions to [0,1] range
        normalized_y = (y_positions + half_side) / (2 * half_side)
        # Test against a uniform distribution
        ks_statistic, _ = stats.kstest(normalized_y, 'uniform')
        if np.isnan(ks_statistic):
            return 0
        return 1 - ks_statistic

    def run(self, output_path) -> float:
        cells = load_alive_cells(output_path)
        if (len(cells) == 0):
            return 0
        inside = 0
        outside = 0
        total = len(cells)
        if (self.function_type == SpatialEvaluationFunctionType.LINEAR):
            for cell in cells:
                x = cell[0]
                y = cell[1]
                if (abs(x - self.center[0]) > self.half_side or abs(y - self.center[1]) > self.half_side):
                    outside += 1
                else:
                    inside += 1
            return -(min(total, 350)) + outside - inside
        else:
            x_positions = []
            y_positions = []
            for cell in cells:
                x = cell[0]
                y = cell[1]
                if (abs(x - self.center[0]) > self.half_side or abs(y - self.center[1]) > self.half_side):
                    outside += 1
                else:
                    inside += 1
                    x_positions.append(x - self.center[0])
                    y_positions.append(y - self.center[1])
            if (inside == 0):
                return outside
            x_positions = np.array(x_positions)
            y_positions = np.array(y_positions)
            
            x_uniformity = SquaredEvaluationFunction.test_x_uniformity(x_positions, self.half_side)
            y_uniformity = SquaredEvaluationFunction.test_y_uniformity(y_positions, self.half_side)
            
            score = (x_uniformity + y_uniformity) / 2            
            return outside - (inside * score)


if __name__== "__main__":
    # Example usage
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "path_to_output"
    print("Path: ", path)
    evaluation_function = CircularEvaluationFunction(center=(0, 0), radius=100, function_type=SpatialEvaluationFunctionType.LINEAR)
    score = evaluation_function.run(path)
    print(f"Function score: {score}")