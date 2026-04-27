# Note: as data extraction is expensive, the output is protected. Upon changes in upstream data, or config. changes, it must be explicitly
# overwritten.
rule data_extraction_hpc:
    input:
        filtered_models = config["filtered_output_dir"],
    output:
        extraction_dir = protected(directory(config["extraction_times_dir"]))
    params:
        remote_user = config["remote_user"],
        remote_host = config["remote_host"],
        remote_base = config["extraction_remote_base"],
        remote_results = config["extraction_remote_results"],
        run_script = config["extraction_remote_script"],
        grid_size = config["extraction_grid_size"],
        max_concurrent = config["extraction_max_concurrent"],
        save_time = config["extraction_save_time"],
        max_retries = config["extraction_max_retries"],
        stale_minutes = config["extraction_stale_minutes"],
        init_pos_json = config["extraction_init_pos_json"],
        times_dir = config["extraction_times_dir"],
        base_output_dir = config["extraction_results_dir"]
    shell:
        """
        python workflow/scripts/data_extraction_hpc.py \\
            --remote-user '{params.remote_user}' \\
            --remote-host '{params.remote_host}' \\
            --remote-base '{params.remote_base}' \\
            --remote-results '{params.remote_results}' \\
            --run-script '{params.run_script}' \\
            --grid-size {params.grid_size} \\
            --max-concurrent {params.max_concurrent} \\
            --save-time {params.save_time} \\
            --max-retries {params.max_retries} \\
            --stale-minutes {params.stale_minutes} \\
            --base-mount-path '{params.base_output_dir}' \\
            --init-pos-json '{params.init_pos_json}' \\
            --input-pool {input.filtered_models} \\
            --times-dir '{params.times_dir}'
        """

rule data_extraction_generate_manifest:
    input:
        extraction_dir = rules.data_extraction_hpc.output.extraction_dir
    output:
        manifest = config["extraction_results_dir"] + "/multiscale_simulations_manifest.json"
    shell:
        """
        python workflow/scripts/data_extraction_generate_manifest.py \
            --mnt-root '{input.extraction_dir}' \
            --output '{output.manifest}'
        """