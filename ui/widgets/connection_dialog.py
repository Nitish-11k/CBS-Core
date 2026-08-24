from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout
)
from PySide6.QtCore import Qt

class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗 Connect to Database (ODBC)")
        self.setFixedSize(400, 220)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title_lbl = QLabel("Enter Target Database Connection Details")
        title_lbl.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(title_lbl)
        
        form_layout = QFormLayout()
        
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("e.g. MyTargetDSN (from ODBC Data Sources)")
        
        self.uid_input = QLineEdit()
        self.uid_input.setPlaceholderText("Username (Leave blank for Windows Auth)")
        
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("Password")
        self.pwd_input.setEchoMode(QLineEdit.Password)
        
        form_layout.addRow("ODBC DSN Name:", self.dsn_input)
        form_layout.addRow("User ID:", self.uid_input)
        form_layout.addRow("Password:", self.pwd_input)
        
        layout.addLayout(form_layout)
        
        from PySide6.QtWidgets import QCheckBox
        self.offline_cb = QCheckBox("Run in Offline/Test Mode (No Real DB connection)")
        self.offline_cb.setChecked(True)
        layout.addWidget(self.offline_cb)
        
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("✔️ Connect & Fetch")
        self.btn_connect.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 5px;")
        self.btn_cancel = QPushButton("❌ Cancel")
        
        self.btn_connect.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_connect)
        
        layout.addLayout(btn_layout)
        
    def get_connection_details(self):
        dsn = self.dsn_input.text().strip()
        uid = self.uid_input.text().strip()
        pwd = self.pwd_input.text().strip()
        is_offline = self.offline_cb.isChecked()
        
        # Simple SQLAlchemy URI construction for pyodbc
        if uid and pwd:
            conn_str = f"mssql+pyodbc://{uid}:{pwd}@{dsn}"
        else:
            conn_str = f"mssql+pyodbc://{dsn}?trusted_connection=yes"
            
        return conn_str, is_offline
