
# This makefile helps to build the singularity container and launch it with the appropriate bindings.

container.sif:
	cd singularity_def && singularity build --fakeroot ../container.sif container.def

launch_container: container.sif
	singularity shell -B physiboss/config_template/:/virtualconfig  -B physiboss/virtualoutput:/virtualoutput container.sif