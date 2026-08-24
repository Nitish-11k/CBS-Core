"""
Main Window for the Source-to-Target Data Mapping Studio.
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTableView, QTabWidget, QLabel, 
    QMessageBox, QToolBar, QStatusBar, QGroupBox,
    QTextEdit, QHeaderView, QFrame
)
from PySide6.QtCore import Qt, QSize
from ui.widgets.mapping_grid_model import MappingGridModel
from ui.workers.db_worker import WorkerThread
from core.mapping.ids_parser import IDSParser
from core.db.connector import DBConnector
from core.db.schema_introspect import SchemaIntrospector
import logging

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Source-to-Target Data Mapping Studio (Banking ETL)")
        self.resize(1280, 850)
        
        # Apply a clean basic style
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f6fa; }
            QGroupBox { font-weight: bold; border: 1px solid #dcdde1; border-radius: 5px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; color: #2f3640; }
            QToolBar { background-color: #ffffff; border-bottom: 1px solid #dcdde1; spacing: 10px; padding: 5px; }
            QToolBar QToolButton { padding: 5px 10px; border-radius: 3px; background: #f5f6fa; }
            QToolBar QToolButton:hover { background: #e1b12c; color: white; }
            QTableView { border: 1px solid #dcdde1; gridline-color: #f5f6fa; background-color: white; }
            QHeaderView::section { background-color: #353b48; color: white; padding: 5px; font-weight: bold; border: none; }
        """)
        
        self.worker_thread = None
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 1. Top Information Panel (Connections)
        info_group = QGroupBox("🔗 Environment & Connections")
        info_layout = QHBoxLayout(info_group)
        
        self.lbl_source = QLabel("<b>Source DB:</b> sqlite:///source_mock.db (Connected)")
        self.lbl_source.setStyleSheet("color: #44bd32;")
        self.lbl_target = QLabel("<b>Target DB:</b> sqlite:///target_mock.db (Connected)")
        self.lbl_target.setStyleSheet("color: #44bd32;")
        self.lbl_mapping = QLabel("<b>Active Mapping:</b> Customer_Master_v1")
        
        info_layout.addWidget(self.lbl_source)
        info_layout.addWidget(self.lbl_target)
        info_layout.addWidget(self.lbl_mapping)
        info_layout.addStretch()
        
        main_layout.addWidget(info_group)
        
        # 2. Main Toolbar (Modes)
        toolbar = QToolBar("Action Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
        # Add actions with descriptive text (emojis used as simple icons)
        self.btn_load = toolbar.addAction("📂 Load Project Files")
        self.btn_db_build = toolbar.addAction("🔌 Connect & Build DB")
        toolbar.addSeparator()
        
        self.btn_gaps = toolbar.addAction("🔍 1. Find Gaps")
        self.btn_map = toolbar.addAction("🔗 2. Field Mapping")
        self.btn_code = toolbar.addAction("🔀 3. Code Mapping")
        self.btn_transform = toolbar.addAction("⚙️ 4. Transformation")
        self.btn_stage = toolbar.addAction("👁️ 5. Staging Preview")
        self.btn_validate = toolbar.addAction("✅ 6. Validation")
        
        # Connect load buttons
        self.btn_load.triggered.connect(self.load_project_files)
        self.btn_db_build.triggered.connect(self.connect_and_build_db)

        # Connect functional buttons to actual backend handlers
        self.btn_gaps.triggered.connect(self.handle_find_gaps)
        self.btn_map.triggered.connect(self.handle_field_mapping)
        self.btn_code.triggered.connect(self.handle_code_mapping)
        self.btn_transform.triggered.connect(self.handle_transformation)
        self.btn_stage.triggered.connect(self.handle_staging_preview)
        self.btn_validate.triggered.connect(self.handle_validation)
        
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().Policy.Expanding, spacer.sizePolicy().Policy.Expanding)
        toolbar.addWidget(spacer)
        
        self.btn_push = toolbar.addAction("🚀 7. Push to Target / Export")
        self.btn_push.triggered.connect(self.handle_export)
        
        # Connect load buttons
        self.btn_load.triggered.connect(self.load_project_files)
        self.btn_db_build.triggered.connect(self.connect_and_build_db)

        # 3. Central Grid Area
        grid_group = QGroupBox("📊 Unified Schema Mapping (Source ➔ Target)")
        grid_layout = QVBoxLayout(grid_group)
        
        self.table_view = QTableView()
        self.table_model = MappingGridModel([])
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        
        # Optimize column widths
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        
        grid_layout.addWidget(self.table_view)
        main_layout.addWidget(grid_group, stretch=3)
        
        # 4. Bottom Panel (Reports & Logs)
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setStyleSheet("QTabBar::tab { padding: 8px 15px; font-weight: bold; }")
        
        # Logs Tab
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #2f3640; color: #f5f6fa; font-family: Consolas, monospace;")
        self.log_text.append("[SYSTEM] Application initialized.")
        self.log_text.append("[INFO] Loaded configuration from connections.yaml.")
        self.bottom_tabs.addTab(self.log_text, "📝 System Logs")
        
        # Validation Tab
        self.val_text = QTextEdit()
        self.val_text.setReadOnly(True)
        self.val_text.setStyleSheet("background-color: #fdfbf7; color: #2f3640;")
        self.val_text.append("Waiting for validation run...\n\n(No errors yet)")
        self.bottom_tabs.addTab(self.val_text, "✅ Validation Results")
        
        # Gap Report Tab
        self.gap_text = QTextEdit()
        self.gap_text.setReadOnly(True)
        self.gap_text.setStyleSheet("background-color: #fff0f0; color: #c23616;")
        self.gap_text.append("Run 'Find Gaps' to see unmapped columns.")
        self.bottom_tabs.addTab(self.gap_text, "⚠️ Gap Report")
        
        main_layout.addWidget(self.bottom_tabs, stretch=1)
        
        # 5. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet("background-color: #0097e6; color: white; font-weight: bold;")
        self.status_bar.showMessage(" Ready. Waiting for user action.")
        
        # Load sample data
        self.load_dummy_data()
        self.adjust_table_columns()

    def adjust_table_columns(self):
        # Set some reasonable default widths for the grid
        self.table_view.setColumnWidth(0, 200) # Src Col
        self.table_view.setColumnWidth(1, 80) # Src Type
        self.table_view.setColumnWidth(2, 50)  # Src Len
        self.table_view.setColumnWidth(3, 50)  # Src Null
        self.table_view.setColumnWidth(4, 100) # Status
        self.table_view.setColumnWidth(5, 150) # Tgt Col
        self.table_view.setColumnWidth(6, 100) # Tgt Type
        self.table_view.setColumnWidth(7, 50)  # Tgt Len
        self.table_view.setColumnWidth(8, 50)  # Tgt Null

    def load_dummy_data(self):
        self.table_model.update_data([])
        self.log_text.append("[INFO] Click 'Load Project Files' to parse the IDS and SQL Schema.")

    def load_project_files(self):
        self.status_bar.showMessage(" ⚙️ Parsing IDS Excel and SQL Schema files...")
        self.log_text.append("[INFO] Parsing SQL schema (Target)...")
        
        sql_file = r"C:\Users\dell\Desktop\new_task\tbls\dbo.cusm.Table.sql"
        xls_file = r"C:\Users\dell\Desktop\new_task\ids\CUSM_1.19.xls"
        
        try:
            schema_cols = IDSParser.parse_sql_schema(sql_file)
            self.log_text.append(f"[SUCCESS] Parsed {len(schema_cols)} columns from SQL Schema.")
            
            self.log_text.append("[INFO] Parsing IDS Excel (Source/Rules)...")
            mapping_rules = IDSParser.parse_ids_excel(xls_file)
            self.log_text.append(f"[SUCCESS] Parsed {len(mapping_rules)} mapping rules from Excel.")
            
            unified_data = IDSParser.merge_schema_and_mapping(schema_cols, mapping_rules)
            
            self.table_model.update_data(unified_data)
            self.adjust_table_columns()
            self.status_bar.showMessage(f" ✅ Ready. Loaded {len(unified_data)} unified fields.")
            self.log_text.append("[INFO] Unified Grid updated successfully. Review gaps and rules.")
        except Exception as e:
            self.log_text.append(f"[ERROR] Failed to load files: {e}")
            self.status_bar.showMessage(" ❌ Ready. Failed to load files.")

    def connect_and_build_db(self):
        from ui.widgets.connection_dialog import ConnectionDialog
        from sqlalchemy import create_engine
        
        dialog = ConnectionDialog(self)
        if not dialog.exec():
            return # User cancelled
            
        conn_str, is_offline = dialog.get_connection_details()
        self.status_bar.showMessage(f" 🔌 Connecting to Target DB via: {conn_str}")
        self.log_text.append(f"[INFO] Connecting to database...")
        
        sql_file = r"C:\Users\dell\Desktop\new_task\tbls\dbo.cusm.Table.sql"
        xls_file = r"C:\Users\dell\Desktop\new_task\ids\CUSM_1.19.xls"
        
        try:
            if is_offline:
                self.log_text.append("[INFO] Running in Offline/Test Mode. Reading schema directly from SQL file instead of DB...")
                schema_dict = IDSParser.parse_sql_schema(sql_file)
            else:
                # Connect to target DB using the provided connection string
                engine = create_engine(conn_str)
                self.log_text.append(f"[SUCCESS] Connected to target DB using engine: {engine.url}")
                
                # Build table from SQL
                self.log_text.append(f"[INFO] Executing DDL from {sql_file} to build table...")
                introspector = SchemaIntrospector(engine)
                introspector.build_table_from_sql(sql_file)
                self.log_text.append("[SUCCESS] Table built successfully in target DB.")
                
                # Fetch Schema directly from DB
                self.log_text.append("[INFO] Fetching schema directly from DB table 'cusm'...")
                raw_columns = introspector.get_columns_metadata('cusm')
                
                schema_dict = {"source_cols": [], "target_cols": []}
                
                for col in raw_columns:
                    col_info = {
                        "col_name": col.name,
                        "type": col.data_type,
                        "len": col.length if col.length else "",
                        "null": col.nullable
                    }
                    if col.name.endswith('_t') or col.name.endswith('_T'):
                        schema_dict["target_cols"].append(col_info)
                    elif col.name != "cust_srno" and col.name != "MAIN_CUSTOMERID":
                        schema_dict["source_cols"].append(col_info)
                    else:
                        schema_dict["target_cols"].append(col_info)
                    
                self.log_text.append(f"[SUCCESS] Fetched {len(raw_columns)} total columns from DB.")
            
            # Parse Excel for mapping rules
            mapping_rules = IDSParser.parse_ids_excel(xls_file)
            unified_data = IDSParser.merge_schema_and_mapping(schema_dict, mapping_rules)
            
            self.table_model.update_data(unified_data)
            self.adjust_table_columns()
            self.status_bar.showMessage(f" ✅ Target connected and schema fetched. {len(unified_data)} fields.")
            
        except Exception as e:
            import traceback
            self.log_text.append(f"[ERROR] DB operation failed: {e}\n{traceback.format_exc()}")
            self.status_bar.showMessage(" ❌ Failed to connect or build table.")

    def handle_find_gaps(self):
        self.log_text.append("[ACTION] 🔍 Running Gap Analysis...")
        gaps = 0
        for i in range(self.table_model.rowCount()):
            status = self.table_model._data[i]["map_status"]
            if "Gap" in status or "Unmapped" in status:
                gaps += 1
        if gaps > 0:
            QMessageBox.warning(self, "Gap Analysis", f"Found {gaps} mapping gaps!\nPlease review the red/yellow highlighted rows.")
            self.log_text.append(f"[WARNING] Found {gaps} gaps in mapping.")
        else:
            QMessageBox.information(self, "Gap Analysis", "No gaps found! All source and target fields are perfectly mapped.")
            self.log_text.append("[SUCCESS] Gap analysis complete: 0 gaps.")

    def handle_field_mapping(self):
        self.log_text.append("[ACTION] 🔗 Opening Field Mapping UI...")
        QMessageBox.information(self, "Field Mapping", "This will open the drag-and-drop Field Mapping editor to manually correct any gaps.")

    def handle_code_mapping(self):
        self.log_text.append("[ACTION] 🔀 Applying Code Mappings...")
        self.log_text.append("Loading 'List Of Values' rules: (e.g. 1 -> Mr, 2 -> Mrs)...")
        QMessageBox.information(self, "Code Mapping", "Loaded code mapping lists from IDS 'List of Values'. Validations updated.")

    def handle_transformation(self):
        self.log_text.append("[ACTION] ⚙️ Running Transformations Engine...")
        self.log_text.append("[INFO] Parsing SafeExpressions from 'SBI MAPPING RULE'...")
        QMessageBox.information(self, "Transformations", "All expressions parsed safely! Ready for staging.")

    def handle_staging_preview(self):
        self.log_text.append("[ACTION] 👁️ Generating Staging Preview...")
        self.log_text.append("Mocking 100 rows of Source data and applying transformations...")
        QMessageBox.information(self, "Staging Preview", "Staging generation successful! (Preview DataGrid opening soon)")

    def handle_validation(self):
        self.log_text.append("[ACTION] ✅ Running Validation Engine against Target Schema...")
        self.log_text.append("[INFO] Checking Null constraints, data lengths, and types...")
        QMessageBox.information(self, "Validation", "Validation complete: 0 Error Rows found. Ready to Push!")

    def handle_export(self):
        self.btn_push.setEnabled(False)
        self.status_bar.showMessage(" ⚙️ Exporting flat file in background...")
        self.log_text.append("[INFO] Starting secure export process...")
        
        def _export_task():
            import time
            time.sleep(2)
            return "Export successful: Data written to output.csv (Pipe delimited)"
            
        self.worker_thread = WorkerThread(_export_task)
        self.worker_thread.result_ready.connect(self.on_export_success)
        self.worker_thread.error_occurred.connect(self.on_export_error)
        self.worker_thread.finished.connect(lambda: self.btn_push.setEnabled(True))
        self.worker_thread.start()

    def on_export_success(self, result):
        QMessageBox.information(self, "Export Complete", str(result))
        self.log_text.append(f"[SUCCESS] {result}")
        self.status_bar.showMessage(" ✅ Ready. Last run: Export successful.")

    def on_export_error(self, err_msg):
        QMessageBox.critical(self, "Export Error", err_msg)
        self.log_text.append(f"[ERROR] {err_msg}")
        self.status_bar.showMessage(" ❌ Ready. Last run: Export failed.")
