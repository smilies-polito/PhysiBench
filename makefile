
# This makefile helps to build the singularity container and launch it with the appropriate bindings.
src/bin/physiboss:
	cd src/bin && \
	mkdir physiboss && cd physiboss && \
	git clone https://github.com/MathCancer/PhysiCell.git && \
	cp -r ../PhysiBench PhysiCell/sample_projects_intracellular/boolean/ && \
	cp ../PhysiBench/Makefile-backup PhysiCell/Makefile && \
	cd PhysiCell/ && make PhysiBench && make

container.sif: src/bin/physiboss
	cd singularity && singularity build --fakeroot ../container.sif container.def

launch_container: container.sif
	mkdir -p src/bin/physiboss/PhysiCell/output && \
	singularity shell -B src/bin/physiboss/PhysiCell/config/:/virtualconfig \
	-B src/bin/physiboss/PhysiCell/output/:/virtualoutput \
	-B ${PWD}:${PWD} container.sif