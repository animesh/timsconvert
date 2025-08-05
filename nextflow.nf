#!~/bin nextflow

nextflow.enable.dsl=2

// params

// required params
params.input = ''

// timsread params
params.ms2_only = 'True'  // only extract MS/MS spectra (default), set to 'False' to also extract MS1

// system params
params.verbose = 'True'

// output directory
params.publishdir = "nf_output"

// Process
process convert {
    publishDir "$params.publishdir", mode: 'copy'

    input:
    path input_file

    output:
    path "*.mgf", emit: mgf
    path "*.txt", emit: ms1, optional: true

    script:
    def ms1_flag = params.ms2_only == 'False' ? "-ms1" : ''
    
    """
    # Ensure timsread is executable
    chmod +x ${workflow.projectDir}/timsread
    
    # Set library path for timsdata SDK and run timsread 
    export LD_LIBRARY_PATH=/mnt/z/Download/timsdata-2.21.0.4/timsdata/linux64
    ${workflow.projectDir}/timsread ${input_file} ${ms1_flag}
    """
}

process summarize {
    publishDir "$params.publishdir", mode: 'copy'

    input:
    path mgf_files
    path ms1_files

    output:
    path "results_file.tsv"

    script:
    """
    # Create a simple summary of the converted files
    echo -e "File\tType\tSize_Lines" > results_file.tsv
    
    # Process MGF files
    for file in ${mgf_files}; do
        if [ -f "\$file" ]; then
            size=\$(wc -l < "\$file" 2>/dev/null || echo 0)
            echo -e "\$file\tMGF\t\$size" >> results_file.tsv
        fi
    done
    
    # Process MS1 files if they exist
    if [ "${ms1_files}" != "null" ]; then
        for file in ${ms1_files}; do
            if [ -f "\$file" ]; then
                size=\$(wc -l < "\$file" 2>/dev/null || echo 0)
                echo -e "\$file\tMS1\t\$size" >> results_file.tsv
            fi
        done
    fi
    """
}


workflow {
    input_ch = Channel.fromPath(params.input, type:'dir', checkIfExists: true)
    converted_data_ch = convert(input_ch)
    
    // Handle optional MS1 files - if no MS1 files are produced, create an empty channel
    ms1_ch = converted_data_ch.ms1.ifEmpty(file('NO_FILE'))
    
    summarize(converted_data_ch.mgf, ms1_ch)
}