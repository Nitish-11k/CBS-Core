"""
Code mapping module.
Holds value-level lookup mappings (e.g., status code '1' -> 'A').
"""
from typing import Dict, Any, List
import yaml
import json
import os

class CodeMappingList:
    def __init__(self, target_col: str):
        self.target_col = target_col
        # source_value -> target_value
        self.map: Dict[str, str] = {}
        # Optional default value if no match is found. If None, it might be flagged as a validation error.
        self.default_value = None

    def add_mapping(self, source_value: str, target_value: str):
        self.map[source_value] = target_value

    def get_target_value(self, source_value: str) -> str:
        return self.map.get(source_value, self.default_value)

class CodeMappingConfig:
    def __init__(self):
        # target_col -> CodeMappingList
        self.mappings: Dict[str, CodeMappingList] = {}

    def add_list(self, mapping_list: CodeMappingList):
        self.mappings[mapping_list.target_col] = mapping_list

    def get_list(self, target_col: str) -> CodeMappingList:
        return self.mappings.get(target_col)

    def to_dict(self):
        result = {}
        for target_col, mapping_list in self.mappings.items():
            result[target_col] = {
                "default": mapping_list.default_value,
                "values": mapping_list.map
            }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        config = cls()
        for target_col, list_data in data.items():
            mapping_list = CodeMappingList(target_col)
            mapping_list.default_value = list_data.get("default")
            values = list_data.get("values", {})
            for src, tgt in values.items():
                mapping_list.add_mapping(str(src), str(tgt))
            config.add_list(mapping_list)
        return config

    def save_to_file(self, filepath: str):
        with open(filepath, 'w') as f:
            if filepath.endswith('.yaml') or filepath.endswith('.yml'):
                yaml.dump(self.to_dict(), f, sort_keys=False)
            else:
                json.dump(self.to_dict(), f, indent=4)

    @classmethod
    def load_from_file(cls, filepath: str):
        if not os.path.exists(filepath):
            return cls()
            
        with open(filepath, 'r') as f:
            if filepath.endswith('.yaml') or filepath.endswith('.yml'):
                data = yaml.safe_load(f) or {}
            else:
                data = json.load(f) or {}
                
        return cls.from_dict(data)
