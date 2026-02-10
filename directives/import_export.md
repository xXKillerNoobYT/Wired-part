# Import/Export SOP

## Purpose
Bulk data import from and export to CSV/Excel files.

## Inputs
- CSV or XLSX file for import
- Export format selection (CSV or XLSX)
- Data type selection (Parts or Jobs)

## Tools
- `src/wired_part/io/csv_handler.py` — CSV import/export
- `src/wired_part/io/excel_handler.py` — Excel import/export
- `src/wired_part/io/validators.py` — data validation
- UI: Import/Export dialogs

## CSV Format (Parts)
```
part_number,description,quantity,min_quantity,location,category,unit_cost,supplier,notes
```

## CSV Format (Jobs)
```
job_number,name,customer,address,status,notes
```

## Import Process
1. User selects file via Browse button
2. File parsed based on extension (.csv or .xlsx)
3. Each row validated (required fields, types, ranges)
4. "Update existing" checkbox controls duplicate handling
5. Results displayed: imported / updated / skipped / errors

## Export Process
1. User selects data type (Parts or Jobs)
2. User selects format (CSV or Excel)
3. Save dialog for destination path
4. File generated with all records

## Validation Rules
- part_number: required, max 50 chars, unique
- description: required
- quantity: integer >= 0
- unit_cost: decimal >= 0
- min_quantity: integer >= 0
- category: must match existing category name (or ignored)

## Excel Header Mapping
- Column headers are normalized (lowercase, spaces to underscores)
- Common variations handled: "Part #" → "part_number", "Qty" → "quantity"

## Edge Cases
- Encoding: UTF-8 expected
- Missing columns: Defaults used (0 for numbers, empty for strings)
- Duplicate part numbers: Skip (default) or Update (if checkbox checked)
