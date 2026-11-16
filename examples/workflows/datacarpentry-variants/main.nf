nextflow.enable.dsl=2
params.samples = null
params.minimum_quality = 100
params.fail_summary = false

process FILTER {
    input:
    path variants
    output:
    path 'filtered.csv'
    script:
    """
    python3 "${projectDir}/analyze.py" filter "${variants}" filtered.csv ${params.minimum_quality}
    """
}

process SUMMARY {
    input:
    path variants
    output:
    path 'summary.tsv'
    script:
    """
    if ${params.fail_summary}; then exit 42; fi
    python3 "${projectDir}/analyze.py" summarize "${variants}" summary.tsv
    """
}

workflow {
    reads = Channel.fromPath(params.samples, checkIfExists: true)
    FILTER(reads)
    SUMMARY(FILTER.out)
}
