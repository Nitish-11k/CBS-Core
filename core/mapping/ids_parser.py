"""
Module for parsing IDS Excel mapping files and SQL schemas.
"""
import pandas as pd
import re
import os
from typing import List, Dict, Any

class IDSParser:
    @staticmethod
    def parse_sql_schema(sql_filepath: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parses a CREATE TABLE SQL script to extract source and target column definitions.
        Target columns are defined below the '---------------new' marker.
        """
        result = {"source_cols": [], "target_cols": []}
        if not os.path.exists(sql_filepath):
            return result
            
        try:
            with open(sql_filepath, 'r', encoding='utf-16le', errors='replace') as f:
                content = f.read()
        except UnicodeError:
            with open(sql_filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
        # Split content at '---------------new'
        parts = re.split(r'-+new', content, flags=re.IGNORECASE)
        source_part = parts[0]
        target_part = parts[1] if len(parts) > 1 else ""
                
        pattern = r'\[([^\]]+)\]\s+\[([^\]]+)\](?:\((\d+)\))?\s+(NULL|NOT NULL)?'
        
        def extract_cols(text_part):
            cols = []
            matches = re.finditer(pattern, text_part)
            for match in matches:
                col_name = match.group(1)
                if col_name.lower() in ['dbo', 'cusm', 'primary']:
                    continue
                data_type = match.group(2)
                length = match.group(3) if match.group(3) else ""
                nullable = True if match.group(4) == "NULL" else False
                cols.append({
                    "col_name": col_name,
                    "type": data_type.upper(),
                    "len": length,
                    "null": nullable
                })
            return cols
            
        result["source_cols"] = extract_cols(source_part)
        result["target_cols"] = extract_cols(target_part)
            
        return result

    @staticmethod
    def parse_ids_excel(excel_filepath: str) -> List[Dict[str, Any]]:
        """Parses the IDS Excel file to extract mapping rules."""
        mappings = []
        if not os.path.exists(excel_filepath):
            return mappings
            
        try:
            # Try to find the sheet that contains mappings
            # We assume it's the first sheet or named 'CUSM_1.19'
            df = pd.read_excel(excel_filepath, sheet_name=0, engine='openpyxl')
        except Exception:
            try:
                df = pd.read_excel(excel_filepath, sheet_name=0)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to read excel: {e}")
                return mappings
                
        # The dataframe should have columns like 'FIELD NAME', 'DATABASE FIELD NAME', 'SBI MAPPING RULE'
        # We need to sanitize column names
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Standardize expected columns
        source_col_name = 'FIELD NAME'
        target_col_name = 'DATABASE FIELD NAME'
        rule_col_name = 'SBI MAPPING RULE'
        
        if source_col_name not in df.columns or target_col_name not in df.columns:
            # Fallback if columns are not found exactly
            return mappings
            
        for _, row in df.iterrows():
            src_col = str(row[source_col_name]).strip() if pd.notna(row[source_col_name]) else ""
            tgt_col = str(row[target_col_name]).strip() if pd.notna(row[target_col_name]) else ""
            rule = str(row[rule_col_name]).strip() if (rule_col_name in df.columns and pd.notna(row[rule_col_name])) else ""
            
            if src_col == 'nan' or not src_col:
                continue
                
            mappings.append({
                "src_col": src_col,
                "src_type": "VARCHAR", # Assume varchar from file usually, or extract from PICTURE CLAUSE
                "tgt_col": tgt_col,
                "rule_expr": rule
            })
            
        return mappings

    @staticmethod
    def merge_schema_and_mapping(schema_dict: Dict[str, List], mappings: List[Dict]) -> List[Dict[str, Any]]:
        """Merges parsed SQL source/target schema and IDS mapping into a unified grid format."""
        result = []
        source_cols = schema_dict.get("source_cols", [])
        target_cols = schema_dict.get("target_cols", [])
        
        # We will match target columns with source columns typically by looking for '_t' suffix or using Excel mapping
        # Create lookups
        src_by_name = {c["col_name"].lower(): c for c in source_cols}
        
        # Excel mappings by target name (if provided)
        excel_by_tgt = {m["tgt_col"].lower(): m for m in mappings if m["tgt_col"]}
        
        for tgt in target_cols:
            tgt_name = tgt["col_name"]
            
            # Try to find corresponding source column in SQL first (e.g. Name_t -> Name)
            possible_src_name = tgt_name
            if tgt_name.endswith('_t'):
                possible_src_name = tgt_name[:-2]
            elif tgt_name.endswith('_T'):
                possible_src_name = tgt_name[:-2]
                
            src_col = src_by_name.get(possible_src_name.lower())
            
            # Try to find rule in Excel mapping
            excel_rule = excel_by_tgt.get(tgt_name.lower())
            
            if src_col:
                rule_text = excel_rule["rule_expr"] if excel_rule else f"Direct map from {possible_src_name}"
                result.append({
                    "src_col": src_col["col_name"],
                    "src_type": src_col["type"],
                    "src_len": src_col["len"],
                    "src_null": src_col["null"],
                    "map_status": "🟢 Mapped",
                    "tgt_col": tgt_name,
                    "tgt_type": tgt["type"],
                    "tgt_len": tgt["len"],
                    "tgt_null": tgt["null"],
                    "rule_expr": rule_text[:50] + "..." if len(rule_text) > 50 else rule_text
                })
            else:
                result.append({
                    "src_col": "",
                    "src_type": "",
                    "src_len": "",
                    "src_null": "",
                    "map_status": "🔴 Target Gap",
                    "tgt_col": tgt_name,
                    "tgt_type": tgt["type"],
                    "tgt_len": tgt["len"],
                    "tgt_null": tgt["null"],
                    "rule_expr": "No Source Match"
                })
                
        # Also add Source columns that didn't map to any target
        tgt_src_names = [r["src_col"].lower() for r in result if r["src_col"]]
        for src in source_cols:
            if src["col_name"].lower() not in tgt_src_names:
                result.append({
                    "src_col": src["col_name"],
                    "src_type": src["type"],
                    "src_len": src["len"],
                    "src_null": src["null"],
                    "map_status": "🟡 Unmapped Src",
                    "tgt_col": "",
                    "tgt_type": "",
                    "tgt_len": "",
                    "tgt_null": "",
                    "rule_expr": ""
                })
                
        return result
