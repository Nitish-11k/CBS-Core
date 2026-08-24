"""
Validation Engine module.
Validates the staged dataset against target schema constraints.
"""
import pandas as pd
from typing import List, Dict, Any, Tuple
from core.db.schema_introspect import ColumnMetadata

class ValidationResult:
    def __init__(self):
        self.pass_count: int = 0
        self.fail_count: int = 0
        self.total_rows: int = 0
        self.failing_rows: pd.DataFrame = pd.DataFrame()
        self.failure_reasons: List[Dict[str, Any]] = [] # list of dicts with row index, col, reason

class ValidationEngine:
    def __init__(self, target_metadata: List[ColumnMetadata]):
        self.target_metadata = {col.name: col for col in target_metadata}

    def validate(self, df: pd.DataFrame) -> ValidationResult:
        result = ValidationResult()
        result.total_rows = len(df)
        
        if result.total_rows == 0:
            return result

        # We keep track of which rows failed and for what reason
        failed_indices = set()
        
        for col_name, meta in self.target_metadata.items():
            if col_name not in df.columns:
                continue
                
            series = df[col_name]
            
            # 1. Not-null check
            if not meta.nullable:
                # pandas isnull() checks for None, NaN, NaT. We also check empty strings just in case
                is_null = series.isnull() | (series.astype(str).str.strip() == '')
                null_indices = is_null[is_null].index
                for idx in null_indices:
                    failed_indices.add(idx)
                    result.failure_reasons.append({
                        "row_index": idx,
                        "column": col_name,
                        "reason": f"Column '{col_name}' is not nullable but contains null/empty value."
                    })
            
            # 2. Length check (for strings)
            if meta.length and meta.data_type.startswith('VARCHAR'):
                # Check length of non-null values
                not_null_series = series[~series.isnull()]
                too_long = not_null_series.astype(str).str.len() > meta.length
                long_indices = too_long[too_long].index
                for idx in long_indices:
                    failed_indices.add(idx)
                    result.failure_reasons.append({
                        "row_index": idx,
                        "column": col_name,
                        "reason": f"Value in '{col_name}' exceeds maximum length of {meta.length}."
                    })

            # 3. Data type check (basic implementation)
            # A full implementation would try to cast to numeric/date and catch errors
            if meta.data_type in ['INTEGER', 'NUMERIC', 'FLOAT']:
                not_null_series = series[~series.isnull()]
                if not pd.api.types.is_numeric_dtype(not_null_series):
                    # Try to convert, find failures
                    coerced = pd.to_numeric(not_null_series, errors='coerce')
                    bad_type_indices = coerced[coerced.isnull()].index
                    for idx in bad_type_indices:
                        failed_indices.add(idx)
                        result.failure_reasons.append({
                            "row_index": idx,
                            "column": col_name,
                            "reason": f"Value in '{col_name}' cannot be cast to numeric."
                        })

        result.fail_count = len(failed_indices)
        result.pass_count = result.total_rows - result.fail_count
        
        if failed_indices:
            result.failing_rows = df.loc[list(failed_indices)]
            
        return result
