from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt

class MultiTableJoinDialog(QDialog):
    def __init__(self, tables, mapping_rules, parent=None):
        super().__init__(parent)
        self.tables = tables
        self.mapping_rules = mapping_rules
        self.setWindowTitle("Auto-Generate Multi-Table Query")
        self.setFixedSize(600, 450)
        self.init_ui()
        self.update_query()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        info = QLabel(f"Detected {len(self.tables)} distinct source tables in your mapping rules:\n{', '.join(self.tables)}\n\nPlease provide the join conditions to link them:")
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(info)
        
        form = QFormLayout()
        self.join_inputs = []
        if len(self.tables) > 1:
            base_table = self.tables[0]
            for table in self.tables[1:]:
                input_field = QLineEdit()
                input_field.setText(f"[{base_table}].[<KEY>] = [{table}].[<KEY>]")
                input_field.textChanged.connect(self.update_query)
                form.addRow(f"Join ➔ {table} ON:", input_field)
                self.join_inputs.append((table, input_field))
        layout.addLayout(form)
        
        layout.addWidget(QLabel("Generated SQL Query (You may edit this manually if joins are complex):"))
        self.query_text = QTextEdit()
        # Set a monospaced font
        font = self.query_text.font()
        font.setFamily("Courier New")
        self.query_text.setFont(font)
        layout.addWidget(self.query_text)
        
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_ok = QPushButton("Execute Query")
        self.btn_ok.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 5px 15px;")
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)
        
    def update_query(self):
        if not self.tables:
            return
            
        base_table = self.tables[0]
        
        select_cols = []
        if hasattr(self, 'mapping_rules') and self.mapping_rules:
            for r in self.mapping_rules:
                t = r.get("src_table", "").strip()
                c = r.get("src_col", "").strip()
                if t and c:
                    select_cols.append(f"[{t}].[{c}] AS [{t}_{c}]")
                    
        if not select_cols:
            select_cols = ["*"]
            
        query = f"SELECT TOP 5000 {', '.join(select_cols)} \nFROM [{base_table}]"
        
        if len(self.tables) > 1:
            for table, input_field in self.join_inputs:
                condition = input_field.text().strip()
                if not condition:
                    condition = f"[{base_table}].[<ENTER_KEY>] = [{table}].[<ENTER_KEY>]"
                query += f"\nLEFT JOIN [{table}] \n  ON {condition}"
                    
        self.query_text.setText(query)
        
    def get_query(self):
        return self.query_text.toPlainText().strip()
