"""
Database writer module.
Writes staged dataset to the target database table safely.
"""
import pandas as pd
from sqlalchemy import Engine
import logging

logger = logging.getLogger(__name__)

class DBWriter:
    def __init__(self, engine: Engine, target_table: str):
        self.engine = engine
        self.target_table = target_table

    def write(self, df: pd.DataFrame, if_exists: str = 'append', chunksize: int = 1000):
        """
        Writes dataframe to the database using SQLAlchemy engine.
        Uses parameterized inserts internally via pandas to_sql.
        """
        try:
            # We explicitly use to_sql with the engine. This uses parameterized queries.
            # Never use string formatting for SQL.
            rows_affected = df.to_sql(
                name=self.target_table,
                con=self.engine,
                if_exists=if_exists,
                index=False,
                chunksize=chunksize,
                method='multi' # Optional, for multi-row insert optimization
            )
            return rows_affected
        except Exception as e:
            logger.error(f"Error writing to target DB: {e}")
            raise
