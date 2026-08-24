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
        # Create an empty dataframe for the target
        target_df = pd.DataFrame()

        for rule in self.mapping_def.rules:
            target_col = rule.target_col
            
            if rule.mode == 'direct':
                if rule.source_col and rule.source_col in source_df.columns:
                    target_df[target_col] = source_df[rule.source_col]
                else:
                    logger.warning(f"Source column {rule.source_col} not found for direct mapping to {target_col}")
                    target_df[target_col] = pd.Series(dtype='object')
            
            elif rule.mode == 'constant':
                target_df[target_col] = rule.constant_value
            
            elif rule.mode == 'expression':
                if rule.source_col and rule.source_col in source_df.columns:
                    series = source_df[rule.source_col]
                else:
                    # If no source col, pass an empty series or dummy
                    series = pd.Series(index=source_df.index, dtype='object')
                    
                if rule.expression:
                    target_df[target_col] = self.parser.apply_rule(series, rule.expression, source_df)
                else:
                    target_df[target_col] = series
            
            # Apply code mapping if one exists for this target column
            code_list = self.code_map_config.get_list(target_col)
            if code_list:
                # Map using pandas map, filling unmatched with default_value if provided
                mapped_series = target_df[target_col].astype(str).map(code_list.map)
                if code_list.default_value is not None:
                    mapped_series = mapped_series.fillna(code_list.default_value)
                target_df[target_col] = mapped_series

        return target_df
