rule run_physiboss_by_id:
    output:
        out_dir = directory(config["simulations_run_base_output"] + "/by_id/{manifest_id}")
    params:
        script = "workflow/scripts/run_physiboss_from_model.py",
        base_models_dir = config["filtered_output_dir_flattened"],
        treatment_duration = config["protocol_treatment_duration"],
        treatment_period = config["protocol_treatment_period"],
        xmin = config["protocol_xmin"],
        xmax = config["protocol_xmax"],
        ymin = config["protocol_ymin"],
        ymax = config["protocol_ymax"],
        ip_type = config["ip_type"],
        ip_center_x = config["ip_center_x"],
        ip_center_y = config["ip_center_y"],
        ip_density = config["ip_density"],
        ip_cell_type = config["ip_cell_type"],
        ip_mode = config["ip_mode"],
        ip_length = config["ip_length"]
    shell:
        """
        python {params.script} \
            --base-models-dir {params.base_models_dir} \
            --output-dir {output.out_dir} \
            --manifest-id {wildcards.manifest_id} \
            --treatment-duration {params.treatment_duration} \
            --treatment-period {params.treatment_period} \
            --xmin {params.xmin} \
            --xmax {params.xmax} \
            --ymin {params.ymin} \
            --ymax {params.ymax} \
            --ip-type {params.ip_type} \
            --ip-center-x {params.ip_center_x} \
            --ip-center-y {params.ip_center_y} \
            --ip-density {params.ip_density} \
            --ip-cell-type {params.ip_cell_type} \
            --ip-mode {params.ip_mode} \
            --ip-length {params.ip_length}
        """

rule run_physiboss_by_name:
    output:
        out_dir = directory(config["simulations_run_base_output"] + "/by_name/{model_family}/{model_name}")
    params:
        script = "workflow/scripts/run_physiboss_from_model.py",
        base_models_dir = config["filtered_output_dir_flattened"],
        treatment_duration = config["protocol_treatment_duration"],
        treatment_period = config["protocol_treatment_period"],
        xmin = config["protocol_xmin"],
        xmax = config["protocol_xmax"],
        ymin = config["protocol_ymin"],
        ymax = config["protocol_ymax"],
        ip_type = config["ip_type"],
        ip_center_x = config["ip_center_x"],
        ip_center_y = config["ip_center_y"],
        ip_density = config["ip_density"],
        ip_cell_type = config["ip_cell_type"],
        ip_mode = config["ip_mode"],
        ip_length = config["ip_length"]
    shell:
        """
        python {params.script} \
            --base-models-dir {params.base_models_dir} \
            --output-dir {output.out_dir} \
            --model-family {wildcards.model_family} \
            --model-name {wildcards.model_name} \
            --treatment-duration {params.treatment_duration} \
            --treatment-period {params.treatment_period} \
            --xmin {params.xmin} \
            --xmax {params.xmax} \
            --ymin {params.ymin} \
            --ymax {params.ymax} \
            --ip-type {params.ip_type} \
            --ip-center-x {params.ip_center_x} \
            --ip-center-y {params.ip_center_y} \
            --ip-density {params.ip_density} \
            --ip-cell-type {params.ip_cell_type} \
            --ip-mode {params.ip_mode} \
            --ip-length {params.ip_length}
        """
