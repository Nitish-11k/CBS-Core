import pytest
import pandas as pd
from core.validation.validation_engine import ValidationEngine
from core.db.schema_introspect import ColumnMetadata

def test_validation_engine():
    # Setup target metadata
    target_metadata = [
        ColumnMetadata(name="id", data_type="INTEGER", nullable=False, is_pk=True),
        ColumnMetadata(name="status", data_type="VARCHAR", nullable=False, length=10),
        ColumnMetadata(name="amount", data_type="NUMERIC", nullable=True)
    ]
    
    engine = ValidationEngine(target_metadata)
    
    # Setup data
    data = pd.DataFrame({
        "id": [1, 2, None], # Row 2 fails (null id)
        "status": ["NEW", "VERY_LONG_STATUS", ""], # Row 1 fails (length), Row 2 fails (empty string not nullable)
        "amount": [100.5, "not_a_number", None] # Row 1 fails (not numeric), Row 2 passes (null allowed)
    })
    
    result = engine.validate(data)
    
    assert result.total_rows == 3
    # Row 0: passes (id=1, status=NEW, amount=100.5)
    # Row 1: fails length on status, fails numeric on amount
    # Row 2: fails not-null on id, fails not-null on status (empty string)
    assert result.fail_count == 2
    assert result.pass_count == 1
    
    reasons = result.failure_reasons
    assert len(reasons) == 4
    
    # Check failure reasons for row 2 (index 2)
    row_2_reasons = [r for r in reasons if r["row_index"] == 2]
    assert any("not nullable" in r["reason"] and r["column"] == "id" for r in row_2_reasons)
    assert any("not nullable" in r["reason"] and r["column"] == "status" for r in row_2_reasons)
    
    # Check failure reasons for row 1 (index 1)
    row_1_reasons = [r for r in reasons if r["row_index"] == 1]
    assert any("exceeds maximum length" in r["reason"] and r["column"] == "status" for r in row_1_reasons)
    assert any("cannot be cast to numeric" in r["reason"] and r["column"] == "amount" for r in row_1_reasons)
