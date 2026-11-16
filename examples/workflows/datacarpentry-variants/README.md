# Data Carpentry processed-variant example

A small SaigenBio-authored Nextflow teaching pipeline for the [Data Carpentry processed E. coli variant table](https://raw.githubusercontent.com/datacarpentry/genomics-r-intro/main/episodes/data/combined_tidy_vcf.csv), already referenced in SaigenBio's E. coli tutorial. This is not an official Data Carpentry Nextflow pipeline and does not call variants.

FILTER retains rows with QUAL >= minimum_quality (default 100). SUMMARY counts retained variants by sample_id. `fail_summary=true` deliberately fails the summary process to test recording. It uses local Python 3 and no containers or third-party Python libraries.

Copy the pipeline to an external analysis workspace before running. See [the integration check](../../../docs/nextflow.md#reproduce-the-real-test) for the full SaigenBio plan, approval, execution and output checks. Do not put generated Nextflow files or downloaded data in this source directory.
