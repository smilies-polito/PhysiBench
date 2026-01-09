

# Build Singularity container
container.sif:
	cd singularity_def && singularity build --fakeroot ../container.sif container.def

open_shell:
	singularity shell -B physiboss/config_template/:/virtualconfig  -B physiboss/virtualoutput:/virtualoutput container.sif