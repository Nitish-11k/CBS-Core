"""
Flat file writer module.
Exports transformed dataframe to CSV or TXT format.
Adheres to strict banking rules:
- Pipe (|) delimited
- Nulls are empty strings, no 'NaN' or 'None'
"""
import pandas as pd
import os

class FlatFileWriter:
    def __init__(self, filepath: str, include_header: bool = True, encoding: str = 'utf-8', lineterminator: str = '\n'):
        self.filepath = filepath
        self.include_header = include_header
        self.encoding = encoding
        self.lineterminator = lineterminator

    def write(self, df: pd.DataFrame):
        """
        Writes the dataframe to the configured file path.
        Enforces empty strings for nulls and pipe delimiter.
        """
        # Strictly enforce pipe delimiter
        sep = '|'
        
        # Enforce nulls as empty string (missing value string in pandas to_csv is na_rep)
        na_rep = ''

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)

        # write to csv
        df.to_csv(
            self.filepath,
            sep=sep,
            na_rep=na_rep,
            header=self.include_header,
            index=False,
            encoding=self.encoding,
            lineterminator=self.lineterminator,
            # We don't want quoting around values ideally unless they contain the delimiter
            # But the requirement says nulls must render as nothing (123||ABC)
            # So double quotes around empty strings should be avoided if possible.
            # to_csv with na_rep='' naturally produces empty strings between delimiters.
        )
