import pandas as pd

out = []
# Read SQL
try:
    with open(r'C:\Users\dell\Desktop\new_task\tbls\dbo.cusm.Table.sql', 'r', encoding='utf-16le', errors='replace') as f:
        sql_content = f.read(2000)
    out.append("--- SQL FILE PREVIEW ---")
    out.append(sql_content)
except Exception as e:
    out.append(f"Error reading SQL: {e}")

# Read Excel
try:
    df_dict = pd.read_excel(r'C:\Users\dell\Desktop\new_task\ids\CUSM_1.19.xls', sheet_name=None, engine='openpyxl')
    out.append("\n\n--- EXCEL FILE PREVIEW ---")
    for sheet_name, df in df_dict.items():
        out.append(f"\nSheet: {sheet_name}")
        out.append(df.head(15).to_string())
except Exception as e:
    out.append(f"Error reading Excel with openpyxl: {e}")
    try:
        df_dict = pd.read_excel(r'C:\Users\dell\Desktop\new_task\ids\CUSM_1.19.xls', sheet_name=None)
        out.append("\n\n--- EXCEL FILE PREVIEW (default engine) ---")
        for sheet_name, df in df_dict.items():
            out.append(f"\nSheet: {sheet_name}")
            out.append(df.head(15).to_string())
    except Exception as e2:
        out.append(f"Error reading Excel with default engine: {e2}")

with open('preview_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
