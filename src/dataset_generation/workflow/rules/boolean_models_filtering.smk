# 1- Run sampling required for sensitivity analysis
rule sampling:
    input:
        pool = config["mutated_boolean_models_dir"],
    output:
        sampling = directory(config["sampling_dir"]),
    params:
        n_contexts = config["sampling_number_of_contexts"],
        n_subjects = config["sampling_number_of_subjects"],
        use_remote = "--use-remote" if config.get("use_remote", False) else "",
        remote_url = lambda wildcards: f"--remote-url {config['remote_url']}" if config.get("remote_url") else "",
        remote_results = lambda wildcards: f"--remote-results-path {config['remote_results_path']}" if config.get("remote_results_path") else "",
        remote_failed = lambda wildcards: f"--remote-failed-path {config['remote_failed_path']}" if config.get("remote_failed_path") else "",
        remote_temp = lambda wildcards: f"--remote-temp-path {config['remote_temp_path']}" if config.get("remote_temp_path") else "",
        max_jobs_stop = config.get("max_jobs_stop", 480),
        max_jobs_resume = config.get("max_jobs_resume", 210),
        hpc_script_name = config.get("hpc_script_name", "")
    shell:
        """
        python workflow/scripts/offline_sampling.py \
            {params.n_contexts} \
            {params.n_subjects} \
            {input.pool} \
            {output.sampling} \
            {params.use_remote} \
            {params.remote_url} \
            {params.remote_results} \
            {params.remote_failed} \
            {params.remote_temp} \
            --max-jobs-stop {params.max_jobs_stop} \
            --max-jobs-resume {params.max_jobs_resume}
            --remote-script-name {params.hpc_script_name}
        """

rule filtering:
    input:
        sampling = config["sampling_dir"],
    output:
        filtering = directory(config["filtering_output_dir"]),
        filtered_models = directory(config["filtered_output_dir"]),
    params:
        mean_threshold = config["mean_threshold"],
        abs_std_threshold = config["abs_std_threshold"],
        norm_std_threshold = config["norm_std_threshold"],
        output_dir = config["filtering_output_dir"],
        filtered_output_dir = config["filtered_output_dir"],
        mutated_models_pool = config["mutated_boolean_models_dir"]
    shell:
        """
        export OUTPUT_DIR={params.output_dir} && \
        export MAIN_DIR={input.sampling} && \
        export MEAN_THRESHOLD={params.mean_threshold} && \
        export ABS_STD_THRESHOLD={params.abs_std_threshold} && \
        export NORM_STD_THRESHOLD={params.norm_std_threshold} && \
        export FILTERED_OUTPUT_DIR={params.filtered_output_dir} && \
        export MUTATED_BOOLEAN_MODELS_DIR={params.mutated_models_pool} && \
        jupyter nbconvert --to notebook --execute \
        --allow-errors \
        --ExecutePreprocessor.timeout=-1 \
        --output-dir={params.output_dir} \
        --output=sensitivity_analysis_output.ipynb \
        workflow/scripts/sensitivity_analysis.ipynb
                """


rule static_distances:
    input:
        mutated_models = config["filtered_output_dir"]
    output:
        static_distances_dir = directory(config["static_distance_dir"])
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