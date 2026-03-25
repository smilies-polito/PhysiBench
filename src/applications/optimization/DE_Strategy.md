
# Optimization strategy for DE

## Why DE and limitations:
* DE is an excellent global optimizer that is naturally scale-invariant.
* DE handles the discretization of continuous variables into binary ones without significant issues (contrarily to discrete, multi value parameters).
* *Implicit sampling* is a standard and effective DE tactic for stochastic functions.
* *Limitation*: : DE is generally sample-inefficient. It requires many generations to converge. With 12 parameters and implicit sampling, 5000 evaluations is on the lower end.



## Parameters:
* Population size: absolute value of 60 to 100 (popsize=5 to popsize=8 in Scipy implementation).
* Mutation Factor (F): Use dithering between 0.5 and 0.9. In noisy environments, a fixed mutation factor can cause the population to stall. Randomizing **F** on a generation-by-generation or individual-by-individual basis helps maintain diversity and prevents premature convergence around "lucky" noisy evaluations. In Scipy implementation, tuple (0.5, 0.9).
* Crossover Probability (CR): moderate value 0.5.
* Strategy: **rand1bin**.
    * rand1bin: hihgly robust to noise, slow to converge.
    * randtobest1bin: faster to converge, less resistant to noise.
    * Best... strategies not suitable for noisy fitness.
