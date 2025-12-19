# 1- Run sampling required for sensitivity analysis
rule sampling:
    input:
        pool = config["mutated_boolean_models_dir"],
    output:
        sampling = directory(config["sampling_dir"]),
    shell:
        """
        python workflow/scripts/sensitivity_analysis.py \
            {config[sampling_number_of_contexts]} \
            {config[sampling_number_of_subjects]} \
            {input.pool} \
            {output.sampling} \
            {"--use-remote" if config.get("use_remote", False) else ""} \
            {"--remote-url " + config["remote_url"] if config.get("remote_url") else ""} \
            {"--remote-results-path " + config["remote_results_path"] if config.get("remote_results_path") else ""} \
            {"--remote-failed-path " + config["remote_failed_path"] if config.get("remote_failed_path") else ""} \
            {"--remote-temp-path " + config["remote_temp_path"] if config.get("remote_temp_path") else ""} \
            --max-jobs-stop {config.get("max_jobs_stop", 480)} \
            --max-jobs-resume {config.get("max_jobs_resume", 210)}
        """