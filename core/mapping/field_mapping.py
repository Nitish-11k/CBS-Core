"""
Field Mapping module.
Holds and persists the source-to-target field mapping definitions.
"""
import yaml
import json
import os
from typing import List, Dict, Any, Optional

class FieldMappingRule:
    def __init__(self, target_col: str, source_col: Optional[str] = None, mode: str = "direct", 
                 constant_value: Any = None, expression: Optional[str] = None):
        self.target_col = target_col
        self.source_col = source_col
        self.mode = mode # "direct", "constant", "expression"
        self.constant_value = constant_value
        self.expression = expression

    def to_dict(self):
        return {
            "target_col": self.target_col,
            "source_col": self.source_col,
            "mode": self.mode,
            "constant_value": self.constant_value,
            "expression": self.expression
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            target_col=data.get("target_col"),
            source_col=data.get("source_col"),
            mode=data.get("mode", "direct"),
            constant_value=data.get("constant_value"),
            expression=data.get("expression")
        )

class MappingDefinition:
    def __init__(self, name: str, source_table: str, target_table: str):
        self.name = name
        self.source_table = source_table
        self.target_table = target_table
        self.rules: List[FieldMappingRule] = []

    def add_rule(self, rule: FieldMappingRule):
        self.rules.append(rule)

    def get_rule_for_target(self, target_col: str) -> Optional[FieldMappingRule]:
        for rule in self.rules:
            if rule.target_col == target_col:
                return rule
        return None

    def to_dict(self):
        return {
            "name": self.name,
            "source_table": self.source_table,
            "target_table": self.target_table,
            "mappings": [rule.to_dict() for rule in self.rules]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        mapping = cls(
            name=data.get("name", "Untitled"),
            source_table=data.get("source_table", ""),
            target_table=data.get("target_table", "")
        )
        for rule_data in data.get("mappings", []):
            mapping.add_rule(FieldMappingRule.from_dict(rule_data))
        return mapping

    def save_to_file(self, filepath: str):
        with open(filepath, 'w') as f:
            if filepath.endswith('.yaml') or filepath.endswith('.yml'):
                yaml.dump(self.to_dict(), f, sort_keys=False)
            else:
                json.dump(self.to_dict(), f, indent=4)

    @classmethod
    def load_from_file(cls, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Mapping file not found: {filepath}")
            
        with open(filepath, 'r') as f:
            if filepath.endswith('.yaml') or filepath.endswith('.yml'):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
                
        return cls.from_dict(data)
