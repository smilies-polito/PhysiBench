

# Run boolean model mutation pipeline
# -----------------------------------------------------
rule boolean_mutations:
    input:
        source_boolean_models = directory(config["source_boolean_models_dir"])
    output:
        mutated_boolean_models = directory(config["mutated_boolean_models_dir"])
        tmp = temp(directory(f"{config['mutated_boolean_models_dir']}.tmp"))
    shell:
        """
        python workflow/scripts/create_boolean_variants.py \
            {output.tmp} \
            {input.source_boolean_models} \
            {config[target_number_of_models]}
        mv {output.tmp} {output.mutated_boolean_models}
        """
