"""
Safe expression parser for transformations.
No arbitrary eval() or exec() is allowed here to comply with banking security rules.
"""
import pandas as pd
import re

class SafeExpressionParser:
    """
    Parses and applies predefined string-based operations to a pandas series or dataframe.
    Allowed operations (examples):
      - trim()
      - uppercase()
      - lowercase()
      - substring(start, length)
      - concat([col1, col2])
    """

    def __init__(self):
        # We can expand this with safe registered functions.
        pass

    def apply_rule(self, series: pd.Series, expression: str, df: pd.DataFrame = None) -> pd.Series:
        """
        Applies a safe rule to a series.
        """
        expr = expression.strip().lower()
        
        if expr == 'trim()':
            return series.astype(str).str.strip()
        elif expr == 'uppercase()':
            return series.astype(str).str.upper()
        elif expr == 'lowercase()':
            return series.astype(str).str.lower()
        elif expr.startswith('concat('):
            # Very basic concat parsing for example: concat(col1, col2)
            match = re.match(r'concat\((.*)\)', expr)
            if match and df is not None:
                cols = [c.strip() for c in match.group(1).split(',')]
                # Filter valid columns
                valid_cols = [c for c in cols if c in df.columns]
                if valid_cols:
                    # Concat with empty string where null
                    return df[valid_cols].fillna('').astype(str).agg(''.join, axis=1)
            # Fallback
            return series

        # If it doesn't match a known safe pattern, we don't execute it.
        # We just return the original series or log an error.
        import logging
        logging.getLogger(__name__).warning(f"Unrecognized or unsafe expression: {expression}. Skipping.")
        return series
