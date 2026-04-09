# Knowledge Compiler: Normalize Rules
**Version**: v1.0
**Layer**: Parsed → Canonical
**Source**: Phase1 ReportSpec v1.1

---

## 1. Normalization Pipeline

```
Parsed Layer → Terminology Mapping → Unit Conversion → Duplicate Detection → Canonical Layer
```

---

## 2. Terminology Alias Table

### 2.1 Velocity Notations
| Alias | Canonical | Context |
|-------|-----------|---------|
| `u` | `u` | x-direction velocity |
| `v` | `v` | y-direction velocity |
| `velocity` | `u` | Generic velocity (assume x-direction) |
| `velocity_x` | `u` | Explicit x-velocity |
| `velocity_y` | `v` | Explicit y-velocity |
| `u/u_ref` | `u*` | Normalized velocity |
| `v/v_ref` | `v*` | Normalized velocity |

### 2.2 Coordinate Notations
| Alias | Canonical |
|-------|-----------|
| `x/H` | `x*` |
| `y/H` | `y*` |
| `x/L` | `x*` (L = characteristic length) |
| `normalized_x` | `x*` |
| `normalized_y` | `y*` |

### 2.3 Error Metric Notations
| Alias | Canonical |
|-------|-----------|
| `RMSE` | `L2` |
| `root_mean_square_error` | `L2` |
| `mean_absolute_error` | `L1` |
| `relative_error` | `ε_rel` |
| `abs_error` | `ε_abs` |

### 2.4 Performance Metric Notations
| Alias | Canonical |
|-------|-----------|
| `Ct` | `Ct` (thrust coefficient — IEC 61400-12) |
| `CP` | `Cp` (power coefficient — uppercase → lowercase) |
| `power_coefficient` | `Cp` |

---

## 3. Variable Symbol Standards

### 3.1 Phase1 ReportSpec v1.1 Canonical Symbols
```
u_ref   — reference velocity (m/s)
u*      — u / u_ref
x*, y*  — x/L, y/H (dimensionless coordinates)
Cp      — pressure coefficient (dimensionless)
Ct      — thrust coefficient (dimensionless)
Cp_max  — maximum power coefficient (dimensionless)
TSR     — tip speed ratio (dimensionless)
ψ       — streamfunction (m²/s)
L1      — mean absolute error
L2      — RMSE
ε_rel   — relative error (%)
ε_abs   — absolute error
GCI     — grid convergence index (%)
```

---

## 4. Unit Conversion Rules

### 4.1 SI Base Units (Required)
- All velocities in m/s
- All lengths in m
- All areas in m²
- All pressures in Pa
- All forces in N

### 4.2 Non-SI Handling
If input uses non-SI (mm, cm, km/h):
- Convert to SI before storing
- Record original unit in `original_unit` field
- Document conversion factor in `unit_conversion_history`

---

## 5. Duplicate and Conflict Detection

### 5.1 Duplicate Detection
Two units are duplicates if:
- Same `source_file` + same `source_line_range` → same artifact
- Same `unit_id` + different `normalized_form` → CONFLICT

### 5.2 Conflict Resolution
Priority (highest to lowest):
1. Later version of spec takes precedence (e.g. v1.1 > v1.0)
2. More specific source (e.g. primary data > derived data)
3. Higher extraction confidence score

### 5.3 Conflict Types
- **Terminology conflict**: Same concept with different symbols → use canonical symbol from alias table
- **Value conflict**: Same field with different values → flag for human review
- **Structure conflict**: Same unit ID with different schema → escalate to canonical review

---

## 6. Data Gap Handling

### 6.1 Known Gaps (Pre-Declared)
| Source | Missing Data | Canonical Handling |
|--------|-------------|-------------------|
| Williamson 1996 / BENCH-04 seed | Full lift/drag time history | Set `data_gaps: ["wake trace detail"]`, do NOT fabricate |

### 6.2 Gap Propagation
- Raw gaps → propagate to Parsed layer
- Parsed gaps → propagate to Canonical layer
- Executable layer must handle gaps gracefully (skip validation for missing data)

---

## 7. Canonical Output Requirements

Each canonical unit must include:
1. `canonical_id`: `CANON-{unit_type}-{seq_num}`
2. `spec_version`: `"v1.1"` (hardcoded)
3. `terminology_map`: Applied alias mappings
4. `conflict_flags`: Empty list if no conflicts
5. `data_gaps`: Empty list if no gaps
