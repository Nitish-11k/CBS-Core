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
