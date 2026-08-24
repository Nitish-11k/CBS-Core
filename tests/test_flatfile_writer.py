import pytest
import pandas as pd
import os
from core.export.flatfile_writer import FlatFileWriter

def test_flatfile_writer_delimiter_and_nulls(tmp_path):
    # Setup test dataframe
    data = {
        'id': [1, 2, 3],
        'status': ['NEW', None, 'DONE'],
        'amount': [100.5, float('nan'), 200.0]
    }
    df = pd.DataFrame(data)
    
    # Path for output file
    output_file = tmp_path / "output.csv"
    
    # Write using our strictly configured writer
    writer = FlatFileWriter(filepath=str(output_file), include_header=True)
    writer.write(df)
    
    # Assert file exists
    assert output_file.exists()
    
    # Read raw content to assert pipe delimiters and blank nulls
    with open(output_file, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
        
    assert len(lines) == 4 # 1 header + 3 data rows
    
    # Header check
    assert lines[0] == "id|status|amount"
    
    # Row 1 check
    assert lines[1] == "1|NEW|100.5"
    
    # Row 2 check (NULL values!)
    # Should be "2||" because both status and amount are null/nan
    assert lines[2] == "2||"
    
    # Row 3 check
    assert lines[3] == "3|DONE|200.0"
    
    # Test text file as well
    txt_file = tmp_path / "output.txt"
    writer_txt = FlatFileWriter(filepath=str(txt_file), include_header=False)
    writer_txt.write(df)
    
    with open(txt_file, 'r', encoding='utf-8') as f:
        lines_txt = f.read().splitlines()
        
    assert len(lines_txt) == 3
    assert lines_txt[1] == "2||" # No header, row 2 is index 1
