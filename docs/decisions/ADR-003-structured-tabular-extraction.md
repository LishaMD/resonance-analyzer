# ADR-003: Dedicated Structured Extractor for Tabular Data

**Date:** April 2026  
**Status:** In Progress  

## Context
Diagnostic testing across 7 runs showed tabular signal recall at 4/28 (14%).
Chunker was treating xlsx/csv files as prose, producing vague semantic 
representations of financial data. P&L anomalies, budget ratios, and CRM 
distributions were consistently missed. Overall recall 23% — Critical Gap.

## Decision
Add structured_extractor.py as a dedicated pipeline branch between app.py 
and chunker.py. Intercepts xlsx and csv files. Extracts as key-value pairs 
and mini data tables. Chunker receives pre-interpreted structured content 
rather than raw tabular data.

## Options Considered
- Improve chunker prompting — rejected: structural problem, not a prompt problem
- Post-processing pass on raw chunks — rejected: garbage in, garbage out  
- Dedicated extractor branch — chosen

## Architecture Impact
Pipeline now has a conditional branch at ingestion:
- xlsx/csv → structured_extractor.py → chunker.py
- All other file types → chunker.py directly (unchanged)

## Open Questions
- Where do real client files live? (PRD decision pending)
- Verify BGE-M3 embeds key-value representations cleanly
- Test recall improvement on tabular signals after implementation

## Consequences
Tabular signals should move from 4/28 toward target. Must rerun full 
golden set test after implementation to measure actual lift.