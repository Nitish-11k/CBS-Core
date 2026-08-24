"""
Staging manager module.
Materializes the transformed dataset in memory using pandas.
Provides methods to retrieve the data for validation, push, or export.
"""
import pandas as pd
from typing import Optional

class StagingManager:
    def __init__(self):
        self._staged_data: Optional[pd.DataFrame] = None

    def stage_data(self, df: pd.DataFrame):
        """Stores the transformed dataframe in the staging area."""
        # We copy it to ensure we don't accidentally modify the source referenced dataframe
        self._staged_data = df.copy()

    def get_staged_data(self) -> Optional[pd.DataFrame]:
        """Retrieves the currently staged dataframe."""
        return self._staged_data

    def clear(self):
        """Clears the staging area to free memory."""
        self._staged_data = None
        
    def get_row_count(self) -> int:
        """Returns the number of rows in the staged dataset."""
        if self._staged_data is not None:
            return len(self._staged_data)
        return 0
