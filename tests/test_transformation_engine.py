import pytest
import pandas as pd
from core.transform.transformation_engine import TransformationEngine
from core.mapping.field_mapping import MappingDefinition, FieldMappingRule
from core.mapping.code_mapping import CodeMappingConfig, CodeMappingList

def test_transformation_engine():
    # Setup Mapping Definition
    mapping_def = MappingDefinition("Test", "source", "target")
    
    # Direct mapping
    mapping_def.add_rule(FieldMappingRule(target_col="out_id", source_col="in_id", mode="direct"))
    # Constant mapping
    mapping_def.add_rule(FieldMappingRule(target_col="status", mode="constant", constant_value="ACTIVE"))
    # Expression mapping
    mapping_def.add_rule(FieldMappingRule(target_col="name_upper", source_col="in_name", mode="expression", expression="uppercase()"))
    # Code mapping
    mapping_def.add_rule(FieldMappingRule(target_col="type_code", source_col="in_type", mode="direct"))
    
    # Setup Code Mapping
    code_config = CodeMappingConfig()
    code_list = CodeMappingList("type_code")
    code_list.add_mapping("1", "A")
    code_list.add_mapping("2", "B")
    code_list.default_value = "UNKNOWN"
    code_config.add_list(code_list)
    
    engine = TransformationEngine(mapping_def, code_config)
    
    # Source Data
    source_df = pd.DataFrame({
        "in_id": [1, 2, 3],
        "in_name": ["Alice", "Bob", "Charlie"],
        "in_type": ["1", "3", None]
    })
    
    target_df = engine.transform(source_df)
    
    assert list(target_df.columns) == ["out_id", "status", "name_upper", "type_code"]
    
    # Check direct
    assert list(target_df["out_id"]) == [1, 2, 3]
    
    # Check constant
    assert list(target_df["status"]) == ["ACTIVE", "ACTIVE", "ACTIVE"]
    
    # Check expression (uppercase)
    assert list(target_df["name_upper"]) == ["ALICE", "BOB", "CHARLIE"]
    
    # Check code mapping
    # '1' -> 'A'
    # '3' -> 'UNKNOWN' (default)
    # None -> 'UNKNOWN'
    assert list(target_df["type_code"]) == ["A", "UNKNOWN", "UNKNOWN"]
