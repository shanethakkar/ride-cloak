"""RideCloak pipeline: ingest -> validate -> classify -> transform -> export -> attest.

Pure-function core (validate/classify/transform) takes DataFrames in and returns
DataFrames plus an audit-record dict out. All file/DB I/O lives in pipeline.io.
"""
