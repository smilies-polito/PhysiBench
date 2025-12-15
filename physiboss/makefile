

physiboss_base:
	git clone https://github.com/MathCancer/PhysiCell

replace_files: physiboss_base
	cp custom_files/main.cpp PhysiCell/main.cpp
	cp custom_files/PhysiCell_various_outputs.cpp PhysiCell/modules/PhysiCell_various_outputs.cpp
	cp custom_files/PhysiCell_various_outputs.h PhysiCell/modules/PhysiCell_various_outputs.h
	cp -r custom_files/config_template PhysiCell/config_template
	cp custom_file/Makefile PhysiCell/Makefile

build_physiboss: replace_fles
	cd PhysiCell && make

all: build_physiboss