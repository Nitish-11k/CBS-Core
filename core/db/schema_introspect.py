"""
Schema introspection module.
Reads table and column metadata using SQLAlchemy Inspector.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import inspect, Table, MetaData

class ColumnMetadata:
    def __init__(self, name: str, data_type: str, nullable: bool, length: Optional[int] = None, precision: Optional[int] = None, is_pk: bool = False):
        self.name = name
        self.data_type = data_type
        self.nullable = nullable
        self.length = length
        self.precision = precision
        self.is_pk = is_pk

    def to_dict(self):
        return {
            "name": self.name,
            "data_type": self.data_type,
            "nullable": self.nullable,
            "length": self.length,
            "precision": self.precision,
            "is_pk": self.is_pk
        }

class SchemaIntrospector:
    def __init__(self, engine):
        self.engine = engine
        self.inspector = inspect(self.engine)

    def get_table_names(self) -> List[str]:
        """Returns a list of all table names in the database."""
        return self.inspector.get_table_names()

    def get_columns_metadata(self, table_name: str) -> List[ColumnMetadata]:
        """Returns metadata for all columns in the specified table."""
        columns_info = self.inspector.get_columns(table_name)
        pk_constraint = self.inspector.get_pk_constraint(table_name)
        pk_columns = pk_constraint.get("constrained_columns", []) if pk_constraint else []
        
        metadata_list = []
        for col in columns_info:
            col_type = col['type']
            
            # Extract length and precision safely
            length = getattr(col_type, 'length', None)
            precision = getattr(col_type, 'precision', None)
            
            # Use string representation of the type
            type_str = str(col_type).upper()
            
            is_pk = col['name'] in pk_columns
            
            metadata_list.append(ColumnMetadata(
                name=col['name'],
                data_type=type_str,
                nullable=col.get('nullable', True),
                length=length,
                precision=precision,
                is_pk=is_pk
            ))
            
        return metadata_list

    def build_table_from_sql(self, sql_filepath: str):
        """Reads a SQL DDL script and executes it against the connected database to build the table."""
        from sqlalchemy import text
        import os
        
        if not os.path.exists(sql_filepath):
            raise FileNotFoundError(f"SQL file not found: {sql_filepath}")
            
        try:
            with open(sql_filepath, 'r', encoding='utf-16le', errors='replace') as f:
                content = f.read()
        except UnicodeError:
            with open(sql_filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
        # Split by GO for SQL Server scripts
        statements = [s.strip() for s in content.split('GO') if s.strip()]
        
        with self.engine.connect() as conn:
            with conn.begin():
                for stmt in statements:
                    if stmt:
                        conn.execute(text(stmt))
