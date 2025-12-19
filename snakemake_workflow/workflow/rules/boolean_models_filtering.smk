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
    shell:
        """
        python workflow/scripts/sensitivity_analysis.py \
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
        """