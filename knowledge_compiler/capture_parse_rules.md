# Knowledge Compiler: Capture & Parse Rules
**Version**: v1.0
**Layer**: Raw → Parsed
**Source**: Phase1 ReportSpec v1.1

---

## 1. Parsing Pipeline

```
Raw File → Markdown Parser / PDF Parser / JSON Parser → Structured Data → Parsed Layer
```

### 1.1 Supported Source Formats

| Format | Parser | Output |
|--------|--------|--------|
| Markdown (.md) | `markdown_it` or regex | Section/table/field extraction |
| JSON (.json) | `json.loads` | Direct object mapping |
| YAML (.yaml) | `pyyaml` | Dict structure |
| CSV (.csv) | `pandas.read_csv` | DataFrame |

---

## 2. Markdown Parsing Rules

### 2.1 Section Extraction
- Headers `#` → chapter units (CH-001, CH-002...)
- `##` → sub-chapter units
- Use regex: `^(#{1,3})\s+(.+)$`

### 2.2 Table Extraction
- Pipe-delimited tables → list of dicts
- Header row → field names
- Data rows → values
- Skip empty rows

### 2.3 Formula Extraction
- Inline code blocks (` ```公式``` `) → formula text
- Math notation → normalize to `u/u_ref`, `y/H` style

### 2.4 Metadata Extraction
- YAML front matter (`---...---`) → metadata dict
- Key-value pairs at file top → file-level attributes

---

## 3. Field Mapping Rules

### 3.1 Chapter Fields
```
source_file → raw source file path
section_title → chapter name
section_level → header level (1/2/3)
content_blocks → list of paragraph/text items
```

### 3.2 Data Point Fields
```
case_id → "CASE-{num}"
benchmark → reference citation
data_type → "centerline_velocity" | "thrust_coefficient" | etc.
data_points → [{y_H, u_uref_exp, u_uref_cfd, error_pct}, ...]
```

### 3.3 Formula Fields
```
formula_id → "FORM-{num}"
symbol → "u*", "Cp", "GCI", etc.
definition → full equation text
variables → [{symbol, description, unit}, ...]
error_type → "absolute" | "relative" | "rmse"
```

---

## 4. Anomaly Marking Rules

### 4.1 Zero Reference Values
- When `|u_exp| < 0.01 * u_max`:
  - Mark `zero_reference: true`
  - Flag for absolute error handling
  - Annotate: `"@ near-zero reference"`

### 4.2 Missing Data
- When expected field is absent:
  - Add to `data_gaps` list
  - Do NOT fabricate填补
  - Log: `WARNING: Expected {field} not found in {source_file}`

### 4.3 Outlier Detection
- When `|error_pct| > 10%`:
  - Check if physically explainable (e.g. dynamic stall region)
  - If yes: add `physical_explanation` annotation
  - If no: flag as `potential_outlier`

---

## 5. Missing Value Handling

### 5.1 Required Fields
If a required field is missing from source:
1. Add to `extraction_warnings`
2. Set field to `null`
3. Do NOT default or infer

### 5.2 Optional Fields
If optional field is missing:
1. Set to `null` or omit
2. Document in `extraction_warnings` if omission is significant

### 5.3 Honesty Constraint
> **CRITICAL**: Any data that does NOT exist in the source PDF/report must NOT be fabricated.
> BENCH-04 seed data includes Strouhal number, mean drag coefficient, and wake visualization only.
> Any claim of extracting richer wake traces without provenance is DATA FABRICATION and must be flagged.

---

## 6. Validation After Parse

After parsing each artifact:
1. Verify all required fields present (or flagged)
2. Check data type consistency
3. Verify referencing integrity (raw_id exists)
4. Compute `extraction_confidence` score
5. Log any warnings to extraction report
