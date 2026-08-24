"""
Gap Analysis module.
Computes unmapped/mismatched columns between source and target schemas.
"""
from typing import List, Dict, Any, Tuple
from core.db.schema_introspect import ColumnMetadata
from core.mapping.field_mapping import MappingDefinition

class GapReport:
    def __init__(self):
        self.unmapped_source_cols: List[str] = []
        self.unmapped_target_cols: List[str] = []
        self.type_mismatches: List[Dict[str, Any]] = []

    def to_dict(self):
        return {
            "unmapped_source_cols": self.unmapped_source_cols,
            "unmapped_target_cols": self.unmapped_target_cols,
            "type_mismatches": self.type_mismatches
        }

class GapAnalyzer:
    def __init__(self, source_metadata: List[ColumnMetadata], target_metadata: List[ColumnMetadata], mapping: MappingDefinition):
        self.source_metadata = {col.name: col for col in source_metadata}
        self.target_metadata = {col.name: col for col in target_metadata}
        self.mapping = mapping

    def analyze(self) -> GapReport:
        report = GapReport()
        
        mapped_source_cols = set()
        mapped_target_cols = set()

        for rule in self.mapping.rules:
            mapped_target_cols.add(rule.target_col)
            if rule.source_col and rule.mode == 'direct':
                mapped_source_cols.add(rule.source_col)
                
                # Check for type mismatch if both exist
                src_meta = self.source_metadata.get(rule.source_col)
                tgt_meta = self.target_metadata.get(rule.target_col)
                
                if src_meta and tgt_meta:
                    if src_meta.data_type != tgt_meta.data_type:
                        report.type_mismatches.append({
                            "source_col": src_meta.name,
                            "target_col": tgt_meta.name,
                            "source_type": src_meta.data_type,
                            "target_type": tgt_meta.data_type
                        })

        for src_name in self.source_metadata.keys():
            if src_name not in mapped_source_cols:
                # Need to verify if it's used in expressions, but for simplicity we assume direct mapped for now.
                # In a robust system, we would parse expression dependencies.
                report.unmapped_source_cols.append(src_name)

        for tgt_name in self.target_metadata.keys():
            if tgt_name not in mapped_target_cols:
                report.unmapped_target_cols.append(tgt_name)

        return report
