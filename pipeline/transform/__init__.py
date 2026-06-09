"""Privacy transforms: suppression, pseudonymization, generalization, k-anonymity.

Pure core (DataFrame in -> DataFrame plus an audit-record dict out). Equivalence
classes are also expressible as DuckDB SQL so a full month can be assessed
without loading the raw parquet into pandas (the scale guardrail). Salt and file
I/O live outside these modules.
"""
