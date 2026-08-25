from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QTabWidget, QWidget, QFileDialog, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt

class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database / Schema Connection")
        self.setFixedSize(450, 300)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title_lbl = QLabel("Select Data Source Type")
        title_lbl.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(title_lbl)
        self.tabs = QTabWidget()
        
        # We can add an optional Table Name input at the top if the dialog title suggests it
        self.table_name_input = QLineEdit()
        if "Table:" in self.windowTitle():
            t_name = self.windowTitle().split("Table: ")[1].strip(")")
            self.table_name_input.setText(t_name)
        else:
            self.table_name_input.setPlaceholderText("Enter target table name (if applicable)")
            
        tbl_layout = QFormLayout()
        tbl_layout.addRow("Target Table:", self.table_name_input)
        layout.addLayout(tbl_layout)
        
        # Tab 1: Live DB
        self.tab_db = QWidget()
        db_layout = QVBoxLayout(self.tab_db)
        
        form_layout = QFormLayout()
        
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("e.g. localhost\\SQLEXPRESS or MyDSN")
        
        self.uid_input = QLineEdit()
        self.uid_input.setPlaceholderText("Username (Leave blank for Windows Auth)")
        
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("Password")
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.driver_combo = QComboBox()
        self.driver_combo.addItems([
            "ODBC Driver 17 for SQL Server",
            "SQL Server",
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "<Use DSN Only - No Driver>"
        ])
        
        form_layout.addRow("Driver:", self.driver_combo)
        form_layout.addRow("Server / DSN:", self.dsn_input)
        form_layout.addRow("User ID:", self.uid_input)
        form_layout.addRow("Password:", self.pwd_input)
        
        db_layout.addLayout(form_layout)
        
        self.btn_test = QPushButton("Test Connection")
        self.btn_test.clicked.connect(self.test_connection)
        db_layout.addWidget(self.btn_test, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.tabs.addTab(self.tab_db, "Live Database (ODBC)")
        
        # Tab 2: DDL Script
        self.tab_ddl = QWidget()
        ddl_layout = QVBoxLayout(self.tab_ddl)
        
        self.lbl_ddl_desc = QLabel("Parse schema columns directly from a SQL CREATE TABLE script.")
        ddl_layout.addWidget(self.lbl_ddl_desc)
        
        ddl_file_layout = QHBoxLayout()
        self.ddl_path_input = QLineEdit()
        self.ddl_path_input.setReadOnly(True)
        self.ddl_path_input.setPlaceholderText("Select a .sql file...")
        
        self.btn_browse_ddl = QPushButton("Browse...")
        self.btn_browse_ddl.clicked.connect(self.browse_ddl)
        
        ddl_file_layout.addWidget(self.ddl_path_input)
        ddl_file_layout.addWidget(self.btn_browse_ddl)
        
        ddl_layout.addLayout(ddl_file_layout)
        ddl_layout.addStretch()
        
        self.tabs.addTab(self.tab_ddl, "DDL Script (Offline)")
        
        layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Confirm Selection")
        self.btn_connect.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 5px;")
        self.btn_cancel = QPushButton("Cancel")
        
        self.btn_connect.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_connect)
        
        layout.addLayout(btn_layout)
        
    def browse_ddl(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select SQL DDL File", "", "SQL Files (*.sql);;All Files (*.*)")
        if filepath:
            self.ddl_path_input.setText(filepath)
            
    def get_sqlalchemy_url(self):
        dsn = self.dsn_input.text().strip()
        uid = self.uid_input.text().strip()
        pwd = self.pwd_input.text().strip()
        driver = self.driver_combo.currentText()
        
        if uid and pwd:
            url = f"mssql+pyodbc://{uid}:{pwd}@{dsn}"
        else:
            url = f"mssql+pyodbc://{dsn}?trusted_connection=yes"
            
        if driver != "<Use DSN Only - No Driver>":
            import urllib.parse
            encoded_driver = urllib.parse.quote_plus(driver)
            if "?" in url:
                url += f"&driver={encoded_driver}"
            else:
                url += f"?driver={encoded_driver}"
        return url
            
    def test_connection(self):
        conn_str = self.get_sqlalchemy_url()
        try:
            from sqlalchemy import create_engine
            kwargs = {}
            if conn_str.startswith("mssql+pyodbc"):
                kwargs['use_setinputsizes'] = False
            engine = create_engine(conn_str, **kwargs)
            engine.connect().close()
            QMessageBox.information(self, "Connection Test", "Connection successful!")
        except Exception as e:
            import traceback
            full_traceback = traceback.format_exc()
            QMessageBox.critical(self, "Connection Failed", f"Failed to connect:\n{str(e)}\n\nTraceback:\n{full_traceback}")
        
    def get_connection_details(self):
        is_offline = (self.tabs.currentIndex() == 1)
        if hasattr(self, 'table_name_input'):
            t_name = self.table_name_input.text().strip()
        else:
            t_name = ""
            
        if is_offline:
            return self.ddl_path_input.text().strip(), True, t_name
        else:
            return self.get_sqlalchemy_url(), False, t_name
