"""
Module for parsing IDS Excel mapping files and SQL schemas.
Fully dynamic — works with any IDS Excel or SQL DDL file.
"""
import pandas as pd
import re
import os
from typing import List, Dict, Any, Tuple, Optional

class IDSParser:
    @staticmethod
    def parse_sql_schema(sql_filepath: str) -> Tuple[List[Dict[str, Any]], str]:
        """
        Parses a CREATE TABLE SQL script to extract column definitions.
        Returns (columns_list, table_name).
        """
        cols = []
        if not os.path.exists(sql_filepath):
            raise FileNotFoundError(f"SQL file not found: {sql_filepath}")
            
        # Try multiple encodings
        content = None
        for enc in ['utf-16le', 'utf-16', 'utf-8-sig', 'utf-8', 'latin-1']:
            try:
                with open(sql_filepath, 'r', encoding=enc, errors='replace') as f:
                    content = f.read()
                if content and 'CREATE TABLE' in content.upper():
                    break
            except (UnicodeError, UnicodeDecodeError):
                continue
                
        if not content:
            raise ValueError(f"Could not read SQL file with any known encoding: {sql_filepath}")
        
        # Extract table name dynamically from CREATE TABLE statement
        table_match = re.search(
            r'CREATE\s+TABLE\s+(?:\[?(\w+)\]?\.)?\[?(\w+)\]?\s*\(',
            content,
            re.IGNORECASE
        )
        table_name = table_match.group(2) if table_match else os.path.splitext(os.path.basename(sql_filepath))[0]
        schema_name = table_match.group(1).lower() if (table_match and table_match.group(1)) else ''
        
        # Build dynamic skip list from table/schema names
        skip_names = {'primary', 'unique', 'constraint', 'index', 'foreign', 'key', 'check', 'default'}
        if schema_name:
            skip_names.add(schema_name)
        if table_name:
            skip_names.add(table_name.lower())
            
        # Regex for column definitions: [col_name] [type](length) NULL/NOT NULL
        pattern = r'\[([^\]]+)\]\s+\[([^\]]+)\](?:\((\d+(?:,\s*\d+)?)\))?\s+(NULL|NOT NULL)?'
        matches = re.finditer(pattern, content)
        for match in matches:
            col_name = match.group(1)
            if col_name.lower() in skip_names:
                continue
            data_type = match.group(2).upper()
            length_str = match.group(3) if match.group(3) else ""
            # Handle precision types like NUMERIC(10,2) — take the first number as length
            length = length_str.split(',')[0].strip() if length_str else ""
            nullable = True if match.group(4) == "NULL" else False
            cols.append({
                "col_name": col_name,
                "type": data_type,
                "len": length,
                "null": nullable
            })
            
        if not cols:
            raise ValueError(f"No column definitions found in SQL file: {sql_filepath}")
            
        return cols, table_name

    @staticmethod
    def _detect_excel_columns(df: pd.DataFrame) -> Dict[str, str]:
        """
        Dynamically detects the source, target, and rule columns in an IDS Excel.
        Returns a mapping of logical names to actual column names found.
        """
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Known column name patterns (priority order)
        source_patterns = ['FIELD NAME', 'SOURCE FIELD', 'SOURCE COLUMN', 'SRC_COL']
        target_patterns = ['DATABASE FIELD NAME', 'TARGET FIELD', 'TARGET COLUMN', 'TGT_COL', 'DB FIELD NAME']
        rule_patterns = ['SBI MAPPING RULE', 'MAPPING RULE', 'TRANSFORMATION RULE', 'RULE', 'ANZ MAPPING RULE']
        picture_patterns = ['PICTURE CLAUSE', 'PIC CLAUSE', 'DATA TYPE', 'FORMAT']
        table_patterns = ['DATABASE TABLE NAME', 'TABLE NAME', 'TARGET TABLE']
        
        def find_col(patterns):
            for p in patterns:
                if p in df.columns:
                    return p
            return None
        
        result = {
            'source': find_col(source_patterns),
            'target': find_col(target_patterns),
            'rule': find_col(rule_patterns),
            'picture': find_col(picture_patterns),
            'table': find_col(table_patterns),
        }
        return result

    @staticmethod
    def _parse_picture_clause(pic: str) -> Dict[str, str]:
        """
        Parses a COBOL PICTURE clause like 'PIC 9(03)' or 'PIC X(08)' 
        into a type and length.
        """
        if not pic or pic == 'nan':
            return {"type": "VARCHAR", "len": ""}
            
        pic = pic.strip().upper()
        
        # Match patterns like PIC 9(03), PIC X(08), PIC 9(16), 9(3), X(10)
        m = re.match(r'(?:PIC\s+)?([9XA])\((\d+)\)', pic)
        if m:
            char = m.group(1)
            length = m.group(2)
            if char == '9':
                return {"type": "NUMERIC", "len": length}
            else:
                return {"type": "VARCHAR", "len": length}
        
        # Match patterns like PIC 9999 or PIC XXXX
        m = re.match(r'(?:PIC\s+)?([9X]+)', pic)
        if m:
            chars = m.group(1)
            if chars[0] == '9':
                return {"type": "NUMERIC", "len": str(len(chars))}
            else:
                return {"type": "VARCHAR", "len": str(len(chars))}
                
        return {"type": "VARCHAR", "len": ""}

    @staticmethod
    def parse_ids_excel(excel_filepath: str) -> List[Dict[str, Any]]:
        """Parses the IDS Excel file to extract mapping rules."""
        mappings = []
        if not os.path.exists(excel_filepath):
            raise FileNotFoundError(f"Excel file not found: {excel_filepath}")
            
        try:
            try:
                df = pd.read_excel(excel_filepath, sheet_name=0, engine='openpyxl')
            except Exception:
                df = pd.read_excel(excel_filepath, sheet_name=0)
        except Exception as e:
            raise ValueError(f"Failed to read Excel file '{os.path.basename(excel_filepath)}'. Ensure it is a valid format (.xls or .xlsx). Error: {e}")
        
        # Dynamically detect column names        
        col_map = IDSParser._detect_excel_columns(df)
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        source_col_name = col_map.get('source')
        target_col_name = col_map.get('target')
        rule_col_name = col_map.get('rule')
        picture_col_name = col_map.get('picture')
        table_col_name = col_map.get('table')
        
        if not source_col_name or not target_col_name:
            available = ', '.join(df.columns.tolist())
            raise ValueError(
                f"Excel file missing required columns. Need a source column "
                f"(tried: FIELD NAME, SOURCE FIELD, etc.) and target column "
                f"(tried: DATABASE FIELD NAME, TARGET FIELD, etc.).\n"
                f"Available columns: {available}"
            )
            
        for _, row in df.iterrows():
            src_col = str(row[source_col_name]).strip() if pd.notna(row[source_col_name]) else ""
            tgt_col = str(row[target_col_name]).strip() if pd.notna(row[target_col_name]) else ""
            
            rule = ""
            if rule_col_name and rule_col_name in df.columns:
                rule = str(row[rule_col_name]).strip() if pd.notna(row[rule_col_name]) else ""
            
            # Parse PICTURE CLAUSE for source type info
            src_type = "VARCHAR"
            src_len = ""
            if picture_col_name and picture_col_name in df.columns and pd.notna(row[picture_col_name]):
                pic_info = IDSParser._parse_picture_clause(str(row[picture_col_name]))
                src_type = pic_info["type"]
                src_len = pic_info["len"]
            
            # Get target table name if available
            tgt_table = ""
            if table_col_name and table_col_name in df.columns and pd.notna(row[table_col_name]):
                tgt_table = str(row[table_col_name]).strip()
            
            if src_col == 'nan' or not src_col:
                continue
                
            mappings.append({
                "src_col": src_col,
                "src_type": src_type,
                "src_len": src_len,
                "tgt_col": tgt_col,
                "tgt_table": tgt_table,
                "rule_expr": rule
            })
            
        return mappings

    @staticmethod
    def parse_code_mappings(excel_filepath: str) -> Dict[str, Dict[str, str]]:
        """Parses the 'List Of Values' sheet from the Excel file."""
        code_maps = {}
        if not os.path.exists(excel_filepath):
            raise FileNotFoundError(f"Excel file not found: {excel_filepath}")
            
        try:
            try:
                df = pd.read_excel(excel_filepath, sheet_name='List Of Values', engine='openpyxl')
            except Exception:
                df = pd.read_excel(excel_filepath, sheet_name='List Of Values')
        except Exception:
            # It's fine if the sheet doesn't exist
            return code_maps
            
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Dynamically find the relevant columns
        field_col = None
        value_col = None
        desc_col = None
        for c in df.columns:
            if 'FIELD' in c and 'NAME' in c:
                field_col = c
            elif c in ('VALUE', 'CODE', 'SOURCE VALUE'):
                value_col = c
            elif c in ('DESCRIPTION', 'DESC', 'TARGET VALUE', 'MEANING'):
                desc_col = c
                
        if not field_col or not value_col or not desc_col:
            return code_maps
            
        current_field = None
        for _, row in df.iterrows():
            field_name = str(row[field_col]).strip()
            if field_name != 'nan' and field_name:
                current_field = field_name
                
            val = str(row[value_col]).strip()
            desc = str(row[desc_col]).strip()
            
            if current_field and val != 'nan' and desc != 'nan':
                if current_field not in code_maps:
                    code_maps[current_field] = {}
                code_maps[current_field][val] = desc
                
        return code_maps

    @staticmethod
    def merge_schema_and_mapping(source_cols: List[Dict], target_cols: List[Dict], mappings: List[Dict] = None) -> List[Dict[str, Any]]:
        """Merges parsed SQL source/target schemas and IDS mapping into a unified grid format."""
        if mappings is None:
            mappings = []
            
        result = []
        
        src_by_name = {c["col_name"].lower(): c for c in source_cols} if source_cols else {}
        excel_by_tgt = {}
        for m in mappings:
            tgt = m.get("tgt_col", "")
            if tgt:
                excel_by_tgt[tgt.lower()] = m
        
        # First, iterate through target columns
        for tgt in target_cols:
            tgt_name = tgt["col_name"]
            excel_rule = excel_by_tgt.get(tgt_name.lower())
            
            src_col = None
            rule_text = ""
            if excel_rule:
                src_col = src_by_name.get(excel_rule["src_col"].lower()) if excel_rule.get("src_col") else None
                rule_text = excel_rule.get("rule_expr", "")
            
            if src_col:
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
            elif excel_rule:
                # Has a mapping rule but source col not found in loaded source schema
                result.append({
                    "src_col": excel_rule.get("src_col", ""),
                    "src_type": excel_rule.get("src_type", ""),
                    "src_len": excel_rule.get("src_len", ""),
                    "src_null": "",
                    "map_status": "🟠 Mapped (src not loaded)",
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
                    "rule_expr": "Missing explicit mapping"
                })
                
        # Add Source columns that didn't map to any target
        mapped_src_names = {r["src_col"].lower() for r in result if r["src_col"]}
        for src in source_cols:
            if src["col_name"].lower() not in mapped_src_names:
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
