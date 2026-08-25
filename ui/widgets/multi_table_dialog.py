from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt

class MultiTableJoinDialog(QDialog):
    def __init__(self, tables, parent=None):
        super().__init__(parent)
        self.tables = tables
        self.setWindowTitle("Auto-Generate Multi-Table Query")
        self.setFixedSize(600, 450)
        self.init_ui()
        self.update_query()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        info = QLabel(f"Detected {len(self.tables)} distinct source tables in your mapping rules:\n{', '.join(self.tables)}\n\nPlease provide the common Primary Key (e.g. CUST_NO, ACCT_ID) to link them:")
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(info)
        
        form = QFormLayout()
        self.join_key_input = QLineEdit()
        self.join_key_input.setPlaceholderText("Enter join key...")
        self.join_key_input.textChanged.connect(self.update_query)
        form.addRow("Common Join Key:", self.join_key_input)
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
            
        key = self.join_key_input.text().strip()
        base_table = self.tables[0]
        
        query = f"SELECT TOP 5000 * \nFROM [{base_table}]"
        
        if len(self.tables) > 1:
            for table in self.tables[1:]:
                if key:
                    query += f"\nLEFT JOIN [{table}] \n  ON [{base_table}].[{key}] = [{table}].[{key}]"
                else:
                    query += f"\nLEFT JOIN [{table}] \n  ON [{base_table}].[<ENTER_KEY>] = [{table}].[<ENTER_KEY>]"
                    
        self.query_text.setText(query)
        
    def get_query(self):
        return self.query_text.toPlainText().strip()
