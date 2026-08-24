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
from PySide6.QtGui import QFont, QColor
from ui.widgets.mapping_grid_model import MappingGridModel
from ui.workers.db_worker import WorkerThread
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
        self.btn_gaps = toolbar.addAction("🔍 1. Find Gaps")
        self.btn_map = toolbar.addAction("🔗 2. Field Mapping")
        self.btn_code = toolbar.addAction("🔀 3. Code Mapping")
        self.btn_transform = toolbar.addAction("⚙️ 4. Transformation")
        self.btn_stage = toolbar.addAction("👁️ 5. Staging Preview")
        self.btn_validate = toolbar.addAction("✅ 6. Validation")
        
        # Connect buttons to basic handlers
        self.btn_gaps.triggered.connect(lambda: self.log_text.append("[ACTION] Find Gaps clicked. (Backend logic pending)"))
        self.btn_map.triggered.connect(lambda: self.log_text.append("[ACTION] Field Mapping clicked. (Backend logic pending)"))
        self.btn_code.triggered.connect(lambda: self.log_text.append("[ACTION] Code Mapping clicked. (Backend logic pending)"))
        self.btn_transform.triggered.connect(lambda: self.log_text.append("[ACTION] Transformation clicked. (Backend logic pending)"))
        self.btn_stage.triggered.connect(lambda: self.log_text.append("[ACTION] Staging Preview clicked. (Backend logic pending)"))
        self.btn_validate.triggered.connect(lambda: self.log_text.append("[ACTION] Validation clicked. (Backend logic pending)"))
        
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().Policy.Expanding, spacer.sizePolicy().Policy.Expanding)
        toolbar.addWidget(spacer)
        
        self.btn_push = toolbar.addAction("🚀 7. Push to Target / Export")
        self.btn_push.triggered.connect(self.handle_export)

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
        self.table_view.setColumnWidth(0, 150) # Src Col
        self.table_view.setColumnWidth(1, 100) # Src Type
        self.table_view.setColumnWidth(2, 60)  # Src Len
        self.table_view.setColumnWidth(3, 60)  # Src Null
        self.table_view.setColumnWidth(4, 100) # Status
        self.table_view.setColumnWidth(5, 150) # Tgt Col
        self.table_view.setColumnWidth(6, 100) # Tgt Type
        self.table_view.setColumnWidth(7, 60)  # Tgt Len
        self.table_view.setColumnWidth(8, 60)  # Tgt Null

    def load_dummy_data(self):
        # Adding more realistic dummy data to help the user understand
        dummy = [
            {"src_col": "CUST_ID", "src_type": "INTEGER", "src_len": "", "src_null": False, "map_status": "🟢 Mapped", "tgt_col": "customer_id", "tgt_type": "INTEGER", "tgt_len": "", "tgt_null": False, "rule_expr": "Direct"},
            {"src_col": "F_NAME", "src_type": "VARCHAR", "src_len": 50, "src_null": True, "map_status": "🟢 Mapped", "tgt_col": "first_name", "tgt_type": "VARCHAR", "tgt_len": 100, "tgt_null": True, "rule_expr": "uppercase()"},
            {"src_col": "ACCT_STAT", "src_type": "VARCHAR", "src_len": 1, "src_null": True, "map_status": "🟡 Code Map", "tgt_col": "account_status", "tgt_type": "VARCHAR", "tgt_len": 10, "tgt_null": False, "rule_expr": "'A'->'ACTIVE'"},
            {"src_col": "CREATE_DT", "src_type": "DATE", "src_len": "", "src_null": True, "map_status": "🔴 Gap", "tgt_col": "", "tgt_type": "", "tgt_len": "", "tgt_null": "", "rule_expr": "Unmapped Source"},
            {"src_col": "", "src_type": "", "src_len": "", "src_null": "", "map_status": "🔴 Gap", "tgt_col": "last_updated", "tgt_type": "TIMESTAMP", "tgt_len": "", "tgt_null": False, "rule_expr": "Unmapped Target"}
        ]
        self.table_model.update_data(dummy)
        
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
