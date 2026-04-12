# 36-02 Summary — GS-07 + GS-08

## Completed

- **GS-07**: Added `POST /pipelines/from-gold-standard/{case_id}` endpoint to pipelines.py
- **GS-07**: Endpoint loads ColdStartCase from GoldStandardRegistry, creates PipelineCreate with single GOLDSTANDARD step
- **GS-07**: Returns 404 for unknown case_id
- **GS-08**: Added 4 provenance hash functions to step_wrappers.py
- **GS-08**: run_wrapper computes and returns provenance in diagnostics on SUCCESS
- **GS-08**: Added `SweepDBService.update_case_provenance()` to pipeline_db.py
- **GS-08**: PipelineExecutor calls `update_case_provenance()` after successful run step

## Files Modified

- `api_server/routers/pipelines.py` — from-gold-standard endpoint
- `api_server/services/step_wrappers.py` — provenance hash functions + run_wrapper wiring
- `api_server/services/pipeline_db.py` — update_case_provenance() method
- `api_server/services/pipeline_executor.py` — provenance persistence call

## Verification

All automated tests passed.
