
# Run boolean model mutation pipeline
# -----------------------------------------------------

# 1- Create a base pool of generic boolean models - from each original model
#   a number of generic ones can be created.
rule base_pool:
    input: 
        source_boolean_models = config["source_boolean_models_dir"]
    output: 
        base_pool = directory(f"{config['base_pool_dir']}")
    params:
        num_generic_by_family = config['NUM_GENERICS_BY_FAMILY']
    shell: """
		python workflow/scripts/make_model_generic.py {input.source_boolean_models} {output.base_pool} {params.num_generic_by_family}
	"""

# 2- From the base pool, create a pool of mutated boolean models
rule pool:
    input:
        source_boolean_models = config["base_pool_dir"]
    output:
        mutated_boolean_models = directory(config["mutated_boolean_models_dir"]),
        tmp = temp(directory(f"{config['mutated_boolean_models_dir']}.tmp"))
    params:
        min_dist = config["MIN_DISTANCE"],
        max_tested = config["MAX_TESTED"],
        max_created_nodes = config["MAX_CREATED_NODES"],
        min_mutations = config["MIN_MUTATIONS"],
        max_mutations = config["MAX_MUTATIONS"],
        mutation_probs = " ".join(map(str, config["MUTATION_P"]))
    shell:
        """
        python workflow/scripts/create_boolean_variants.py \
            {output.tmp} \
            {input.source_boolean_models} \
            {config[target_number_of_models]} \
            --min-dist {params.min_dist} \
            --max-tested {params.max_tested} \
            --max-created-nodes {params.max_created_nodes} \
            --min-mutations {params.min_mutations} \
            --max-mutations {params.max_mutations} \
            --mutation-probs {params.mutation_probs}
        mv {output.tmp} {output.mutated_boolean_models}
        """

# 3- Compute graph-based static distance measures between generated models 
rule static_distances:
    input:
        mutated_models = config["mutated_boolean_models_dir"]
    output:
        static_distances_dir = directory("results/boolean_models/static_distance")
    params:
        num_processes = config["STATIC_DISTANCE_NUM_PROCESSES"],
        max_graphs = config["STATIC_DISTANCE_MAX_GRAPHS"],
        use_global = config["STATIC_DISTANCE_USE_GLOBAL"],
        distance_types = config["STATIC_DISTANCE_MEASURES"],
    shell:
        """
            python workflow/scripts/protocols_distance_static.py \
                {input.mutated_models} \
                {output.static_distances_dir} \
                {params.num_processes} \
                {params.max_graphs} \
                {params.use_global} \
                {params.distance_types}
        """