"""
Transformation Engine.
Applies mappings and safe expressions to a pandas DataFrame.
"""
import pandas as pd
from core.mapping.field_mapping import MappingDefinition
from core.mapping.code_mapping import CodeMappingConfig
from core.transform.expression_rules import SafeExpressionParser
import logging

logger = logging.getLogger(__name__)

class TransformationEngine:
    def __init__(self, mapping_def: MappingDefinition, code_map_config: CodeMappingConfig):
        self.mapping_def = mapping_def
        self.code_map_config = code_map_config
        self.parser = SafeExpressionParser()

    def transform(self, source_df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms the source dataframe into the target dataframe based on mapping rules.
        """
        # Start with all source columns to preserve them in the final staged data
        # This prevents the final DataFrame from being reduced to only explicitly mapped columns
        target_dict = {c: source_df[c] for c in source_df.columns}
        
        # Create a case-insensitive lookup map for source columns
        col_map = {str(c).lower(): c for c in source_df.columns}

        for rule in self.mapping_def.rules:
            target_col = rule.target_col
            result_series = pd.Series(index=source_df.index, dtype='object')
            
            # Case insensitive search
            actual_src_col = None
            if rule.source_col:
                # Try exact match first, then case-insensitive, then strip prefixes (e.g. T1.col_name)
                if rule.source_col in source_df.columns:
                    actual_src_col = rule.source_col
                elif str(rule.source_col).lower() in col_map:
                    actual_src_col = col_map[str(rule.source_col).lower()]
                else:
                    # sometimes source_col is 'Table_Name.ColName'
                    pure_col = str(rule.source_col).split('.')[-1].lower()
                    if pure_col in col_map:
                        actual_src_col = col_map[pure_col]

            if rule.mode == 'direct':
                if actual_src_col:
                    result_series = source_df[actual_src_col]
                else:
                    logger.warning(f"Source column {rule.source_col} not found for direct mapping to {target_col}")
            
            elif rule.mode == 'constant':
                result_series = pd.Series(rule.constant_value, index=source_df.index)
            
            elif rule.mode == 'expression':
                if actual_src_col:
                    series = source_df[actual_src_col]
                else:
                    series = pd.Series(index=source_df.index, dtype='object')
                    
                if rule.expression:
                    result_series = self.parser.apply_rule(series, rule.expression, source_df)
                else:
                    result_series = series
            
            # Apply code mapping if one exists for this target column
            code_list = self.code_map_config.get_list(target_col)
            if code_list:
                mapped_series = result_series.astype(str).map(code_list.map)
                if code_list.default_value is not None:
                    mapped_series = mapped_series.fillna(code_list.default_value)
                result_series = mapped_series
                
            target_dict[target_col] = result_series

        # Construct DataFrame all at once to avoid fragmentation warnings
        return pd.DataFrame(target_dict)
