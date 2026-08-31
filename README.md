# EZ_Culture_MT5_Automation

Official technical source-of-truth repository for PROJECT_EZ_Culture MT5 automation.

## Scope

- MT5 MQL5 source and controlled technical scripts
- Validation, health-check, compile and deployment-gate tooling
- MASTER SPEC
- Protection rules
- Schemas
- TASK and validation documentation

## Runtime Separation

- GitHub: Technical Source of Truth
- F Drive: Local operating source, runtime data, EX5, CSV/XLSX
- Google Drive: Research reports and control-readable reports/data
- MT5: Live runtime

## Safety

Do not commit:

- Broker credentials
- Passwords
- API keys
- OAuth/PAT tokens
- Google credentials
- Runtime raw data
- CSV/XLSX
- EX5
- Backup archives

## Change Flow

RESEARCH -> REVIEW -> TASK -> CODE -> VALIDATION -> USER APPROVAL -> DEPLOY

Automatic deployment to live MT5 is prohibited unless explicitly approved by the user.