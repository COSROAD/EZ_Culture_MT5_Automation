# PROJECT_EZ_Culture MASTER SPEC

## Roles

- GitHub: official technical source of truth.
- Local operating root: `F:\마켓 프리존\EZ_컬쳐캐피탈-Auto`.
- Git workspace: `C:\GitHub\EZ_Culture_MT5_Automation`.
- Google Drive: research reports, latest reports, and control-readable data.
- MT5: live runtime.

## Control flow

RESEARCH -> REVIEW -> TASK -> CODE -> VALIDATION -> USER APPROVAL -> DEPLOY -> RUNTIME VALIDATION -> RESEARCH FEEDBACK

## End-to-end data principle

GENERATED -> LOCAL_SAVED -> AGGREGATED -> DRIVE_SYNCED -> CONTROL_READABLE -> REVIEWED

## Execution principle

EXECUTION -> TARGET_REACHED -> OUTPUT_UPDATED -> DATA_FRESH -> DRIVE_DELIVERED -> CONTROL_RECEIVED -> REVIEWED

Any missing required stage is a FAIL for that end-to-end path.

## Absolute rules

- Automatic live MT5 deployment is prohibited.
- Production replacement without explicit user approval is prohibited.
- Runtime data must not be committed to GitHub.
- Secret values must not be committed.
- Direct `git init` in the F-drive operating root is prohibited.
- Analysis results are TASK candidates only; they do not authorize automatic code changes.