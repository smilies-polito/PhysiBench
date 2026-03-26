
# This makefile helps to build the singularity container and launch it with the appropriate bindings.

container.sif:
	cd singularity && singularity build --fakeroot ../container.sif container.def

launch_container: container.sif
	singularity shell -B src/bin/physiboss/PhysiCell/config/:/virtualconfig -B ${PWD}:${PWD} container.sif