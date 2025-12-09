from sklearn.neighbors import NearestNeighbors
import numpy as np 

"""
Utils file that contains distance computation classes and functions.
"""

def normalize_vector_1D(vec):
    vec = np.asarray(vec)
    centered = vec - np.mean(vec)
    norm = np.linalg.norm(centered)
    if norm == 0:
        return centered 
    return centered / norm

def normalize_vector_2D(vec):
    return np.array([normalize_vector_1D(vec[i]) for i in range(vec.shape[0])])

def normalize_vector_flattened(vec):
    return normalize_vector_1D(vec.flatten())
def correlation_nn_1d(a, b):
    a = np.ravel(a)
    b = np.ravel(b)
    corr_matrix = np.corrcoef(a, b)
    if (np.isnan(corr_matrix).any() or np.isinf(corr_matrix).any()) or (np.isinf(corr_matrix).any() or np.isnan(corr_matrix).any()):
        return 0
    r = abs(corr_matrix[0, 1])
    if r < 0 or r > 1:
        r = 1
    distance = 1 - r
    return distance

def correlation_distance_nn_avg(p1, p2):
    p1, p2 = normalize_vector_2D(p1), normalize_vector_2D(p2)
    return np.mean([correlation_nn_1d(p1[i], p2[i]) for i in range(N_TIME_STEPS)])

def correlation_distance_nn_flattened(p1, p2):
    return correlation_nn_1d(p1, p2)

class CorrelationDistances:
    def __init__(self):
        self.elements = []

    def add_element(self, element):
        element = normalize_vector_flattened(element)
        self.elements.append(element)
    
    def test_element(self, element):
        element = normalize_vector_flattened(element)
        distance = 10
        for e in self.elements:
            d = correlation_distance_nn_flattened(e, element)
            distance = min(distance, d)
        return distance

class CorrelationDistancesAll:
    def __init__(self, elements):
        self.elements = elements
        for i in range(len(self.elements)):
            self.elements[i] = normalize_vector_flattened(self.elements[i])

    def get_max_distances(self):
        distances = []
        for i in range(len(self.elements)):
            max_distance = 0
            for j in range(0, len(self.elements)):
                if i == j:
                    continue
                d = correlation_distance_nn_flattened(self.elements[i], self.elements[j])
                if (d==1):
                    return i, j
                max_distance = max(max_distance, d)
            distances.append(max_distance)
        return distances

    
class EuclideanDistance:
    def linear_distance_single_step(p1, p2):
        # p1, p2 are 1D numpy arrays
        return np.linalg.norm(p1 - p2)
    # Compute avg over all time steps
    def linear_distance_avg(p1, p2):
        # p1, p2 are 2D numpy arrays
        return np.mean([EuclideanDistance.linear_distance_single_step(p1[i], p2[i]) for i in range(p1.shape[0])])
    # Consider different time steps as different states - distance on unique 1D vector
    def linear_distance_flattened(p1, p2):
        # p1, p2 are 2D numpy arrays
        return EuclideanDistance.linear_distance_single_step(p1.flatten(), p2.flatten()) / p1.shape[0]
    def test_element(pool, element):
        return [EuclideanDistance.linear_distance_avg(pool[i], element) for i in range(len(pool))]