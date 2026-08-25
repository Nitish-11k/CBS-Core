"""
Main Window for the Source-to-Target Data Mapping Studio.
"""
import os
import traceback
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTableView, QTabWidget, QLabel, 
    QMessageBox, QToolBar, QStatusBar, QGroupBox,
    QTextEdit, QHeaderView, QFrame, QFileDialog,
    QDialog, QComboBox, QDialogButtonBox, QGridLayout
)
from PySide6.QtCore import Qt, QSize, QAbstractTableModel, QModelIndex, QThread, Signal
from ui.widgets.mapping_grid_model import MappingGridModel
from ui.widgets.connection_dialog import ConnectionDialog
from ui.widgets.mapping_grid_model import MappingGridModel
from ui.widgets.loading_spinner import LoadingSpinner
from ui.widgets.multi_table_dialog import MultiTableJoinDialog
from core.mapping.ids_parser import IDSParser

class DataLoaderThread(QThread):
    finished = Signal(object, str, str) # returns (dataframe, error_message, query/table_name)
    
    def __init__(self, query, engine, is_custom, table_name=""):
        super().__init__()
        self.query = query
        self.engine = engine
        self.is_custom = is_custom
        self.table_name = table_name
        
    def run(self):
        try:
            if self.is_custom:
                df = pd.read_sql(self.query, self.engine)
                self.finished.emit(df, "", "Custom SQL Query")
            else:
                try:
                    df = pd.read_sql(f"SELECT TOP 5000 * FROM [{self.table_name}]", self.engine)
                except Exception:
                    df = pd.read_sql_query(f"SELECT * FROM {self.table_name} LIMIT 5000", self.engine)
                self.finished.emit(df, "", self.table_name)
        except Exception as e:
            self.finished.emit(None, str(e), self.table_name)

class TransformationThread(QThread):
    finished = Signal(object, str) # df, error_message
    
    def __init__(self, engine, source_df):
        super().__init__()
        self.engine = engine
        self.source_df = source_df
        
    def run(self):
        try:
            staged = self.engine.transform(self.source_df)
            self.finished.emit(staged, "")
        except Exception as e:
            import traceback
            self.finished.emit(None, f"{str(e)}\n{traceback.format_exc()}")

class PushDataThread(QThread):
    finished = Signal(str, str, int) # error_msg, table_name, rows_pushed
    
    def __init__(self, df, conn_str, table_name, schema_metadata=None):
        super().__init__()
        self.df = df
        self.conn_str = conn_str
        self.table_name = table_name
        self.schema_metadata = schema_metadata
        
    def run(self):
        try:
            from sqlalchemy import create_engine
            from core.db.schema_introspect import SchemaIntrospector
            
            kwargs = {}
            if self.conn_str.startswith("mssql+pyodbc"):
                kwargs['use_setinputsizes'] = False
            engine = create_engine(self.conn_str, **kwargs)
            
            # 1 & 2 & 3: Inspect the actual SQL Server schema of target table
            introspector = SchemaIntrospector(engine)
            actual_db_cols = introspector.get_columns_metadata(self.table_name)
            if not actual_db_cols:
                raise ValueError(f"Table '{self.table_name}' does not exist in the target database or has no columns.")
                
            db_col_names = {c.name.lower(): c.name for c in actual_db_cols}
            
            df_to_push = self.df.copy()
            
            # 7 & 11: Check for duplicate target column names in the dataframe
            # e.g., 'DTSTAMP' and 'DtStamp' -> both map to 'dtstamp' in lower case
            seen = set()
            duplicates = set()
            for col in df_to_push.columns:
                lower_col = str(col).lower()
                if lower_col in seen:
                    duplicates.add(str(col))
                seen.add(lower_col)
                
            if duplicates:
                # Remove duplicate columns, keeping the first occurrence
                df_to_push = df_to_push.loc[:, ~df_to_push.columns.duplicated(keep='first')]
                
            # Auto-rename common mismatched legacy columns to DB columns if they exist
            common_renames = {'custno': 'cust_srno'}
            rename_dict = {}
            for df_col in df_to_push.columns:
                lower_df = str(df_col).lower()
                if lower_df in common_renames and common_renames[lower_df] in db_col_names:
                    rename_dict[df_col] = common_renames[lower_df]
            if rename_dict:
                df_to_push.rename(columns=rename_dict, inplace=True)
                
            # 4, 5, 8: Compare and filter
            cols_to_keep = []
            unmapped_cols = []
            
            for df_col in df_to_push.columns:
                lower_df = str(df_col).lower()
                if lower_df in db_col_names:
                    cols_to_keep.append(df_col)
                else:
                    unmapped_cols.append(str(df_col))
                    
            if not cols_to_keep:
                raise ValueError("None of the dataframe columns match the actual SQL Server target table columns.")
                
            # 10: Log unmapped/ignored fields separately
            warning_msg = ""
            if unmapped_cols:
                warning_msg = f"\nWarning: The following columns were ignored as they do not exist in '{self.table_name}': {', '.join(unmapped_cols)}"
                
            # 8: Final INSERT contains ONLY columns that actually exist in the target table
            df_to_push = df_to_push[cols_to_keep]
            
            # Rename columns to exactly match the target database casing
            df_to_push.columns = [db_col_names[str(c).lower()] for c in df_to_push.columns]
            
            # 11b: Attempt to parse date strings to real pandas datetime objects FAST
            # This fixes SQL Server error 241 (Conversion failed when converting date and/or time from character string)
            # We use coerce so invalid dates become NaT, then replace NaT with None (NULL in SQL Server).
            import re
            import pandas as pd
            date_pattern = re.compile(r'^\d{2,4}[-/]\d{2}[-/]\d{2,4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?$')
            
            def normalize_dates(series):
                # Try multiple formats and combine them
                s1 = pd.to_datetime(series, format='%d-%m-%y', errors='coerce')
                s2 = pd.to_datetime(series, format='%d-%m-%Y', errors='coerce')
                s3 = pd.to_datetime(series, format='%Y-%m-%d', errors='coerce')
                return s1.fillna(s2).fillna(s3)

            for col in df_to_push.columns:
                if df_to_push[col].dtype == 'object':
                    # Check first non-null value to see if it even looks like a date
                    sample = df_to_push[col].dropna()
                    if not sample.empty:
                        first_valid = str(sample.iloc[0]).strip()
                        if date_pattern.match(first_valid):
                            df_to_push[col] = normalize_dates(df_to_push[col])
                            # Replace NaT with None so PyODBC handles it as NULL
                            df_to_push[col] = df_to_push[col].astype(object).where(df_to_push[col].notna(), None)
                            
            # 11: Validate Required Target Columns
            # Verify that required NOT NULL columns exist in the DataFrame before attempting insertion
            missing_required = []
            df_cols_lower = [str(c).lower() for c in df_to_push.columns]
            for col_meta in actual_db_cols:
                # If column is NOT nullable and NOT a primary key (assuming PKs auto-increment)
                if not col_meta.nullable and not col_meta.is_pk:
                    if col_meta.name.lower() not in df_cols_lower:
                        missing_required.append(col_meta.name)
            
            if missing_required:
                raise ValueError(
                    f"Validation Error: Target table '{self.table_name}' requires the following NOT NULL columns, "
                    f"but they are missing from the mapped data:\n\n"
                    f"- Missing Columns: {', '.join(missing_required)}\n"
                    f"- Available Columns: {', '.join(df_to_push.columns)}\n\n"
                    f"Please verify your Excel mapping rules and ensure required source columns exist."
                )
            
            # 12: Execute safely in batches using method='multi'
            # SQL Server supports up to 1000 rows in a single VALUES clause.
            # We use 100 to be extremely safe against memory/timeout freezes with large columns.
            df_to_push.to_sql(self.table_name, engine, if_exists='append', index=False, chunksize=100, method='multi')
            self.finished.emit(warning_msg, self.table_name, len(df_to_push))
        except Exception as e:
            import traceback
            self.finished.emit(f"{str(e)}\n{traceback.format_exc()}", self.table_name, 0)

from ui.workers.db_worker import WorkerThread
from core.db.connector import DBConnector
from core.db.schema_introspect import SchemaIntrospector, ColumnMetadata
from core.mapping.gap_analysis import GapAnalyzer, GapReport
from core.mapping.field_mapping import MappingDefinition, FieldMappingRule
from core.mapping.code_mapping import CodeMappingConfig, CodeMappingList
from core.transform.transformation_engine import TransformationEngine
from core.validation.validation_engine import ValidationEngine
from core.export.flatfile_writer import FlatFileWriter
import pandas as pd
from sqlalchemy import create_engine
import logging

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Source-to-Target Data Mapping Studio (Banking ETL)")
        self.resize(1280, 850)
        
        # Apply a polished Premium Light Theme style
        self.setStyleSheet("""
            QMainWindow { background-color: #f8f9fa; color: #212529; }
            QWidget { font-family: 'Segoe UI', Inter, sans-serif; }
            #sidebar { background-color: #ffffff; border-right: 1px solid #dee2e6; }
            #sidebar QPushButton { background-color: transparent; color: #495057; border: none; border-radius: 4px; font-weight: bold; font-size: 13px; }
            #sidebar QPushButton:hover { background-color: #e9ecef; color: #0d6efd; }
            QGroupBox { font-weight: bold; border: 1px solid #dee2e6; border-radius: 6px; margin-top: 12px; background-color: #ffffff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; color: #0d6efd; }
            QTableView { border: 1px solid #dee2e6; gridline-color: #f1f3f5; background-color: #ffffff; color: #212529; alternate-background-color: #f8f9fa; selection-background-color: #0d6efd; selection-color: #ffffff; }
            QHeaderView::section { background-color: #f8f9fa; color: #495057; padding: 6px; font-weight: bold; border: none; border-right: 1px solid #dee2e6; border-bottom: 1px solid #dee2e6; }
            QPushButton { background-color: #0d6efd; color: #ffffff; border: none; padding: 6px 15px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #0b5ed7; }
            QTextEdit { background-color: #ffffff; color: #212529; border: 1px solid #dee2e6; border-radius: 4px; font-family: Consolas, monospace; }
            QLabel { color: #212529; }
            QTabBar::tab { background: #e9ecef; color: #495057; padding: 8px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; border: 1px solid #dee2e6; border-bottom: none; margin-right: 2px;}
            QTabBar::tab:selected { background: #ffffff; color: #0d6efd; border-top: 2px solid #0d6efd; }
            QTabWidget::pane { border: 1px solid #dee2e6; border-top: none; }
        """)
        
        self.worker_thread = None
        
        # State Management
        self.source_metadata = []
        self.target_metadata = []
        self.mapping_rules = []
        self.code_mappings = {}
        self.staged_data = None
        self.source_data = None
        self.loader_thread = None
        
        self.setup_ui()

    def setup_ui(self):
        # Setup Main Structure with Sidebar
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_hbox = QHBoxLayout(central_widget)
        main_hbox.setContentsMargins(0, 0, 0, 0)
        main_hbox.setSpacing(0)
        
        # Sidebar
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)
        sidebar_layout.setSpacing(10)
        
        self.btn_toggle_sidebar = QPushButton("☰")
        self.btn_toggle_sidebar.setToolTip("Toggle Sidebar")
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        self.btn_toggle_sidebar.setStyleSheet("font-size: 18px; padding: 5px;")
        sidebar_layout.addWidget(self.btn_toggle_sidebar, alignment=Qt.AlignmentFlag.AlignLeft)
        sidebar_layout.addSpacing(20)
        
        # Sidebar buttons
        self.btn_map = QPushButton("1. Field Mapping")
        self.btn_code = QPushButton("2. Code Mapping")
        self.btn_push_src = QPushButton("3. Push Source Staging")
        self.btn_gap_src = QPushButton("4. Source Gaps")
        self.btn_val_src = QPushButton("5. Source Validation")
        self.btn_transform = QPushButton("6. Transform")
        self.btn_push_tgt = QPushButton("7. Push Target Staging")
        self.btn_gap_tgt = QPushButton("8. Target Gaps")
        self.btn_val_tgt = QPushButton("9. Target Validation")
        self.btn_deploy = QPushButton("10. Final Deployment")
        
        self.sidebar_btns = [
            self.btn_map, self.btn_code, self.btn_push_src, self.btn_gap_src, 
            self.btn_val_src, self.btn_transform, self.btn_push_tgt, 
            self.btn_gap_tgt, self.btn_val_tgt, self.btn_deploy
        ]
        
        for btn in self.sidebar_btns:
            btn.setStyleSheet("text-align: left; padding: 10px;")
            sidebar_layout.addWidget(btn)
            
        self.btn_map.clicked.connect(self.handle_field_mapping)
        self.btn_code.clicked.connect(self.handle_code_mapping)
        self.btn_push_src.clicked.connect(self.handle_push_source_staging)
        self.btn_gap_src.clicked.connect(self.handle_find_gaps_source)
        self.btn_val_src.clicked.connect(self.handle_validation_source)
        self.btn_transform.clicked.connect(self.handle_transformation)
        self.btn_push_tgt.clicked.connect(self.handle_push_target_staging)
        self.btn_gap_tgt.clicked.connect(self.handle_find_gaps_target)
        self.btn_val_tgt.clicked.connect(self.handle_validation_target)
        self.btn_deploy.clicked.connect(self.handle_export)
        
        sidebar_layout.addStretch()
        main_hbox.addWidget(self.sidebar)
        
        # Right Content Area
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        main_hbox.addWidget(content_widget, stretch=1)

        # 1. Top Information Panel (Data Sources)

        info_group = QGroupBox("Data Sources")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(10)
        
        self.btn_load_source = QPushButton("Load Source Schema")
        self.btn_load_target = QPushButton("Load Target Schema")
        self.btn_load_mapping = QPushButton("Load IDS Mapping")
        self.btn_load_data = QPushButton("Load Source Data (Live)")
        
        # Override primary blue with secondary gray for these data loader buttons
        for btn in [self.btn_load_source, self.btn_load_target, self.btn_load_mapping, self.btn_load_data]:
            btn.setStyleSheet("background-color: #e9ecef; color: #495057; border: 1px solid #ced4da; padding: 6px 10px;")
        
        self.lbl_source = QLabel("Source: Not Loaded")
        self.lbl_target = QLabel("Target: Not Loaded")
        self.lbl_mapping = QLabel("Mapping: Not Loaded")
        self.lbl_data = QLabel("Data: Mock")
        
        # Make labels elide or wrap if text gets too long
        for lbl in [self.lbl_source, self.lbl_target, self.lbl_mapping, self.lbl_data]:
            lbl.setWordWrap(True)
            lbl.setMinimumWidth(150)
        
        # Row 0
        info_layout.addWidget(self.btn_load_source, 0, 0)
        info_layout.addWidget(self.lbl_source, 0, 1)
        info_layout.addWidget(self.btn_load_target, 0, 2)
        info_layout.addWidget(self.lbl_target, 0, 3)
        
        # Row 1
        info_layout.addWidget(self.btn_load_mapping, 1, 0)
        info_layout.addWidget(self.lbl_mapping, 1, 1)
        info_layout.addWidget(self.btn_load_data, 1, 2)
        info_layout.addWidget(self.lbl_data, 1, 3)
        
        info_layout.setColumnStretch(1, 1)
        info_layout.setColumnStretch(3, 1)
        
        main_layout.addWidget(info_group)
        
        self.btn_load_source.clicked.connect(self.load_source_schema)
        self.btn_load_target.clicked.connect(self.load_target_schema)
        self.btn_load_mapping.clicked.connect(self.load_ids_mapping)
        self.btn_load_data.clicked.connect(self.load_source_data)

        # 3. Central Tabs Area
        self.tabs = QTabWidget()
        
        # Tab 1: Schema Mapping Grid
        self.tab_schema = QWidget()
        grid_layout = QVBoxLayout(self.tab_schema)
        
        self.table_view = QTableView()
        self.table_model = MappingGridModel([])
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setWordWrap(True)
        
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        
        grid_layout.addWidget(self.table_view)
        
        # Tab 2: Data Previews
        self.tab_data = QWidget()
        data_layout = QHBoxLayout(self.tab_data)
        
        self.source_data_view = QTableView()
        self.target_data_view = QTableView()
        
        data_layout.addWidget(self.source_data_view)
        data_layout.addWidget(self.target_data_view)
        
        self.tabs.addTab(self.tab_schema, "Schema Mapping Rules")
        self.tabs.addTab(self.tab_data, "Data Previews (Source vs Target)")
        
        # Add Spinner Overlay (Centered)
        self.spinner = LoadingSpinner(self, size=60, arc_color="#0d6efd", bg_color="#e9ecef")
        self.spinner.hide()
        
        main_layout.addWidget(self.tabs, stretch=3)
        
        # Inline Editing Delegate for Source Column
        from PySide6.QtWidgets import QStyledItemDelegate
        class ComboDelegate(QStyledItemDelegate):
            def __init__(self, main_win):
                super().__init__(main_win)
                self.main_win = main_win
            def createEditor(self, parent, option, index):
                combo = QComboBox(parent)
                src_names = [""] + [c["col_name"] for c in self.main_win.source_metadata]
                combo.addItems(src_names)
                return combo
            def setEditorData(self, editor, index):
                val = index.model().data(index, Qt.ItemDataRole.DisplayRole)
                idx = editor.findText(val) if val else 0
                editor.setCurrentIndex(max(0, idx))
            def setModelData(self, editor, model, index):
                model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

        self.combo_delegate = ComboDelegate(self)
        self.table_view.setItemDelegateForColumn(1, self.combo_delegate)
        self.table_model.dataChanged.connect(self.on_mapping_edited)
        
        # Legend
        legend = QLabel("Legend: Mapped | Unmapped Source (may be dropped) | Target Gap (must map)")
        legend.setStyleSheet("font-style: italic; color: #7f8fa6;")
        grid_layout.addWidget(legend)

        # 4. Bottom Panel (Reports & Logs)
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setStyleSheet("QTabBar::tab { padding: 8px 15px; font-weight: bold; }")
        
        # Logs Tab
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #2f3640; color: #f5f6fa; font-family: Consolas, monospace;")
        self.log_text.append("[SYSTEM] Application initialized.")
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
        self.status_bar.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold;")
        self.status_bar.showMessage(" Ready. Waiting for user action.")
        
        self.adjust_table_columns()

    def show_spinner(self):
        # Center over the main window
        x = (self.width() - self.spinner.width()) // 2
        y = (self.height() - self.spinner.height()) // 2
        self.spinner.move(x, y)
        self.spinner.raise_()
        self.spinner.show()
        for btn in [self.btn_load_source, self.btn_load_target, self.btn_load_mapping, self.btn_load_data]:
            btn.setEnabled(False)
            
    def hide_spinner(self):
        self.spinner.hide()
        for btn in [self.btn_load_source, self.btn_load_target, self.btn_load_mapping, self.btn_load_data]:
            btn.setEnabled(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'spinner') and self.spinner.isVisible():
            x = (self.width() - self.spinner.width()) // 2
            y = (self.height() - self.spinner.height()) // 2
            self.spinner.move(x, y)

    def toggle_sidebar(self):
        if self.sidebar.width() > 100:
            self.sidebar.setFixedWidth(60)
            for btn in self.sidebar_btns:
                btn.setText(btn.text().split(". ")[0]) # Keep number only as icon replacement
                btn.setStyleSheet("text-align: center; padding: 10px;")
        else:
            self.sidebar.setFixedWidth(220)
            # Restore names
            self.btn_map.setText("1. Field Mapping")
            self.btn_code.setText("2. Code Mapping")
            self.btn_push_src.setText("3. Push Source Staging")
            self.btn_gap_src.setText("4. Source Gaps")
            self.btn_val_src.setText("5. Source Validation")
            self.btn_transform.setText("6. Transform")
            self.btn_push_tgt.setText("7. Push Target Staging")
            self.btn_gap_tgt.setText("8. Target Gaps")
            self.btn_val_tgt.setText("9. Target Validation")
            self.btn_deploy.setText("10. Final Deployment")
            for btn in self.sidebar_btns:
                btn.setStyleSheet("text-align: left; padding: 10px;")

    def adjust_table_columns(self):
        self.table_view.setColumnWidth(0, 100) # Src Table
        self.table_view.setColumnWidth(1, 150) # Src Col
        self.table_view.setColumnWidth(2, 80)  # Src Type
        self.table_view.setColumnWidth(3, 50)  # Src Len
        self.table_view.setColumnWidth(4, 50)  # Src Null
        self.table_view.setColumnWidth(5, 100) # Status
        self.table_view.setColumnWidth(6, 150) # Tgt Col
        self.table_view.setColumnWidth(7, 100) # Tgt Type
        self.table_view.setColumnWidth(8, 50)  # Tgt Len
        self.table_view.setColumnWidth(9, 50)  # Tgt Null

    def on_mapping_edited(self, top_left, bottom_right, roles):
        if Qt.ItemDataRole.EditRole in roles or not roles:
            row = top_left.row()
            col = top_left.column()
            if col == 1 or col == 10:
                # Update mapping rules
                new_src = self.table_model._data[row]["src_col"]
                new_rule = self.table_model._data[row].get("rule_expr", "")
                tgt = self.table_model._data[row]["tgt_col"]
                
                rule_found = False
                for r in self.mapping_rules:
                    if r.get("tgt_col", "").lower() == tgt.lower():
                        if col == 1:
                            r["src_col"] = new_src
                        elif col == 10:
                            r["rule_expr"] = new_rule
                        rule_found = True
                        break
                        
                if not rule_found and tgt:
                    self.mapping_rules.append({
                        "src_col": new_src,
                        "tgt_col": tgt,
                        "rule_expr": new_rule
                    })
                
                # Refresh to re-evaluate statuses
                self.refresh_grid()

    def get_schema_from_dialog(self, source_type: str):
        dialog = ConnectionDialog(self)
        dialog.setWindowTitle(f"🔗 Load {source_type} Schema")
        if not dialog.exec():
            return None, None
            
        conn_str, is_offline, t_name = dialog.get_connection_details()
        if is_offline:
            if not conn_str:
                QMessageBox.warning(self, "Warning", "No DDL file selected.")
                return None, None
            try:
                raw_cols, table_name = IDSParser.parse_sql_schema(conn_str, section=source_type.lower())
                cols = []
                for c in raw_cols:
                    meta = ColumnMetadata(
                        name=c["col_name"],
                        data_type=c["type"],
                        length=int(c["len"]) if c["len"] else None,
                        nullable=c["null"],
                        is_pk=False
                    )
                    c["_meta"] = meta
                    c["table_name"] = table_name
                    cols.append(c)
                label = f"DDL: {table_name} ({os.path.basename(conn_str)})"
                self.log_text.append(f"[INFO] Detected table name: '{table_name}' from DDL.")
                return cols, label
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to parse DDL script:\n{e}")
                self.log_text.append(f"[ERROR] Failed to parse DDL script: {e}\n{traceback.format_exc()}")
                return None, None
        else:
            try:
                kwargs = {}
                if conn_str.startswith("mssql+pyodbc"):
                    kwargs['use_setinputsizes'] = False
                engine = create_engine(conn_str, **kwargs)
                introspector = SchemaIntrospector(engine)
                # Ask user which table to introspect
                available_tables = introspector.get_table_names()
                if not available_tables:
                    QMessageBox.warning(self, "Warning", "No tables found in the database.")
                    return None, None
                from PySide6.QtWidgets import QInputDialog
                table_name, ok = QInputDialog.getItem(self, "Select Table", "Choose a table to load:", available_tables, 0, False)
                if not ok or not table_name:
                    return None, None
                raw_columns = introspector.get_columns_metadata(table_name)
                cols = []
                for col in raw_columns:
                    meta = ColumnMetadata(
                        name=col.name,
                        data_type=str(col.data_type),
                        length=col.length if hasattr(col, 'length') and col.length else None,
                        nullable=col.nullable,
                        is_pk=col.is_pk
                    )
                    cols.append({
                        "col_name": meta.name,
                        "type": meta.data_type,
                        "len": meta.length if meta.length else "",
                        "null": meta.nullable,
                        "table_name": table_name,
                        "_meta": meta
                    })
                return cols, f"DB: {table_name} ({engine.url.database or 'Live'})"
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to connect or fetch schema:\n{e}")
                self.log_text.append(f"[ERROR] DB connection failed: {e}\n{traceback.format_exc()}")
                return None, None

    def load_source_schema(self):
        cols, label = self.get_schema_from_dialog("Source")
        if cols is not None:
            self.handle_unified_schema_split(cols, label, "Source")

    def load_target_schema(self):
        cols, label = self.get_schema_from_dialog("Target")
        if cols is not None:
            self.handle_unified_schema_split(cols, label, "Target")

    def handle_unified_schema_split(self, cols, label, default_type):
        has_t = any(c["col_name"].lower().endswith('_t') for c in cols)
        if has_t:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, "Unified Schema Detected", 
                f"Detected columns ending with '_t'. Do you want to automatically split this into Source and Target schemas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                source_cols = [c for c in cols if not c["col_name"].lower().endswith('_t')]
                target_cols = [c for c in cols if c["col_name"].lower().endswith('_t')]
                self.source_metadata = source_cols
                self.target_metadata = target_cols
                self.lbl_source.setText(f"Source: {label} (Split)")
                self.lbl_source.setStyleSheet("color: #44bd32; font-weight: bold;")
                self.lbl_target.setText(f"Target: {label} (Split)")
                self.lbl_target.setStyleSheet("color: #44bd32; font-weight: bold;")
                self.log_text.append(f"[SUCCESS] Split schema: {len(source_cols)} Source, {len(target_cols)} Target columns.")
                self.refresh_grid()
                return

        # Default behavior if no split
        if default_type == "Source":
            self.source_metadata.extend(cols)
            self.lbl_source.setText(f"Source: {len(self.source_metadata)} cols")
            self.lbl_source.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.log_text.append(f"[SUCCESS] Appended {len(cols)} source columns. Total: {len(self.source_metadata)}")
        else:
            self.target_metadata = cols
            self.lbl_target.setText(f"Target: {label}")
            self.lbl_target.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.log_text.append(f"[SUCCESS] Loaded {len(cols)} target columns.")
        self.refresh_grid()

    def load_source_data(self):
        dialog = ConnectionDialog(self)
        dialog.setWindowTitle("📥 Load Source Data (Live DB)")
        if not dialog.exec():
            return
            
        conn_str, is_offline, _ = dialog.get_connection_details()
        if is_offline:
            QMessageBox.warning(self, "Warning", "Data can only be loaded from a Live Database, not a DDL script.")
            return
            
        try:
            kwargs = {}
            if conn_str.startswith("mssql+pyodbc"):
                kwargs['use_setinputsizes'] = False
            engine = create_engine(conn_str, **kwargs)
            introspector = SchemaIntrospector(engine)
            available_tables = introspector.get_table_names()
            if not available_tables:
                QMessageBox.warning(self, "Warning", "No tables found in the database.")
                return
            available_tables.insert(0, "[Custom SQL Query...]")
            
            # Auto-detect multiple source tables from mappings
            unique_src_tables = []
            if hasattr(self, 'mapping_rules') and self.mapping_rules:
                unique_src_tables = list(set([r.get("src_table", "").strip() for r in self.mapping_rules if r.get("src_table", "").strip()]))
            
            if len(unique_src_tables) > 1:
                available_tables.insert(0, "[Auto Multi-Table SQL...]")
                
            from PySide6.QtWidgets import QInputDialog
            table_name, ok = QInputDialog.getItem(self, "Select Table", "Choose table to load data from (TOP 5000):", available_tables, 0, False)
            if not ok or not table_name:
                return
                
            if table_name == "[Auto Multi-Table SQL...]":
                join_dialog = MultiTableJoinDialog(unique_src_tables, self)
                if not join_dialog.exec():
                    self.status_bar.showMessage(" Data load cancelled.")
                    return
                query = join_dialog.get_query()
                if not query:
                    self.status_bar.showMessage(" Data load cancelled (Empty Query).")
                    return
                    
                self.show_spinner()
                self.status_bar.showMessage(" Loading multi-table data...")
                
                self.loader_thread = DataLoaderThread(query, engine, is_custom=True)
                self.loader_thread.finished.connect(self.on_data_loaded)
                self.loader_thread.start()
                
            elif table_name == "[Custom SQL Query...]":
                query, ok2 = QInputDialog.getMultiLineText(self, "Custom SQL Query", "Enter your SELECT query to fetch data (e.g., SELECT TOP 1000 * FROM T1 JOIN T2...):")
                if not ok2 or not query.strip():
                    self.status_bar.showMessage(" Data load cancelled.")
                    return
                self.show_spinner()
                self.status_bar.showMessage(" Loading data...")
                
                self.loader_thread = DataLoaderThread(query, engine, is_custom=True)
                self.loader_thread.finished.connect(self.on_data_loaded)
                self.loader_thread.start()
            else:
                self.show_spinner()
                self.status_bar.showMessage(" Loading data...")
                
                self.loader_thread = DataLoaderThread("", engine, is_custom=False, table_name=table_name)
                self.loader_thread.finished.connect(self.on_data_loaded)
                self.loader_thread.start()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initiate data load:\n{e}")
            self.log_text.append(f"[ERROR] Data load init failed: {e}\n{traceback.format_exc()}")
            self.status_bar.showMessage(" Error.")

    def on_data_loaded(self, df, error, name):
        self.hide_spinner()
        if error:
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{error}")
            self.log_text.append(f"[ERROR] Data load failed: {error}")
            self.status_bar.showMessage(" Data load failed.")
            return
            
        self.source_data = df
        self.lbl_data.setText(f"Data: {len(df)} rows")
        self.lbl_data.setStyleSheet("color: #0d6efd; font-weight: bold;")
        self.log_text.append(f"[SUCCESS] Loaded {len(df)} rows from {name}.")
        self.status_bar.showMessage(" Data loaded.")
        
        # Update the Source Data Preview Tab
        from ui.widgets.mapping_grid_model import DataFrameModel
        model = DataFrameModel(self.source_data)
        self.source_data_view.setModel(model)
        
        QMessageBox.information(self, "Data Loaded", f"Successfully loaded {len(df)} rows.\nYou can view it in the 'Data Previews' tab.")

    def load_ids_mapping(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select IDS Mapping Excel", "", "Excel Files (*.xls *.xlsx);;All Files (*.*)")
        if not filepath:
            return
            
        self.status_bar.showMessage(f" ⚙️ Parsing IDS Excel: {os.path.basename(filepath)}...")
        try:
            self.mapping_rules = IDSParser.parse_ids_excel(filepath)
            self.lbl_mapping.setText(f"Mapping: {os.path.basename(filepath)}")
            self.lbl_mapping.setStyleSheet("color: #44bd32; font-weight: bold;")
            self.log_text.append(f"[SUCCESS] Parsed {len(self.mapping_rules)} mapping rules from Excel.")
            
            # Also parse code mappings
            self.code_mappings = IDSParser.parse_code_mappings(filepath)
            self.log_text.append(f"[SUCCESS] Parsed Code Mappings for {len(self.code_mappings)} fields.")
            
            self.refresh_grid()
            self.status_bar.showMessage(f" ✅ Loaded {len(self.mapping_rules)} rules.")
        except Exception as e:
            QMessageBox.critical(self, "Mapping Load Error", str(e))
            self.log_text.append(f"[ERROR] Failed to load mapping: {e}\n{traceback.format_exc()}")
            self.status_bar.showMessage(" ❌ Failed to load mapping rules.")

    def refresh_grid(self):
        if not self.source_metadata and not self.target_metadata:
            return
        unified_data = IDSParser.merge_schema_and_mapping(self.source_metadata, self.target_metadata, self.mapping_rules)
        self.table_model.update_data(unified_data)
        self.adjust_table_columns()

    def handle_find_gaps(self):
        if not self.target_metadata or not self.source_metadata:
            QMessageBox.warning(self, "Warning", "Please load both Source and Target Schemas first.")
            return
            
        self.log_text.append("[ACTION] 🔍 Running Gap Analysis...")
        
        # Build MappingDefinition from self.mapping_rules
        mapping_def = MappingDefinition("Active", "Source", "Target")
        for r in self.mapping_rules:
            expr = r.get("rule_expr", "")
            is_expr = any(f in expr.lower() for f in ["concat(", "trim(", "uppercase(", "lowercase("])
            mode = "expression" if is_expr else "direct"
            
            mapping_def.add_rule(FieldMappingRule(
                target_col=r.get("tgt_col", ""),
                source_col=r.get("src_col", ""),
                mode=mode,
                expression=r.get("rule_expr", "")
            ))
            
        src_meta = [c["_meta"] for c in self.source_metadata if "_meta" in c]
        tgt_meta = [c["_meta"] for c in self.target_metadata if "_meta" in c]
        
        analyzer = GapAnalyzer(src_meta, tgt_meta, mapping_def)
        report = analyzer.analyze()
        
        self.gap_text.clear()
        self.gap_text.append("=== GAP REPORT ===\n")
        
        gaps = len(report.unmapped_target_cols)
        unmapped_src = len(report.unmapped_source_cols)
        mismatches = len(report.type_mismatches)
        
        for tgt in report.unmapped_target_cols:
            self.gap_text.append(f"[TARGET GAP] Missing source mapping for: {tgt}")
        for src in report.unmapped_source_cols:
            self.gap_text.append(f"[SOURCE UNMAPPED] Will be dropped: {src}")
        for mismatch in report.type_mismatches:
            self.gap_text.append(f"[TYPE MISMATCH] {mismatch['source_col']} ({mismatch['source_type']}) -> {mismatch['target_col']} ({mismatch['target_type']})")
                
        if gaps > 0 or mismatches > 0:
            QMessageBox.warning(self, "Gap Analysis", f"Found {gaps} Target mapping gaps and {mismatches} type mismatches!\nPlease review the Gap Report tab.")
            self.log_text.append(f"[WARNING] Found {gaps} gaps in mapping.")
        else:
            QMessageBox.information(self, "Gap Analysis", "No Target gaps found! All required target fields are mapped.")
            self.log_text.append("[SUCCESS] Gap analysis complete: 0 target gaps.")
            self.gap_text.append("All target columns are successfully mapped!")

    def handle_field_mapping(self):
        """Opens an editable mapping grid to manually link source→target columns."""
        self.log_text.append("[ACTION] 🔗 Opening Field Mapping Editor...")
        
        if not self.source_metadata and not self.target_metadata:
            QMessageBox.warning(self, "Warning", "Please load at least a Source or Target schema first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔗 Field Mapping Editor")
        dialog.resize(900, 500)
        layout = QVBoxLayout(dialog)
        
        info = QLabel("For each target column, select the source column it should map from. Leave blank for gaps.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Build editable table
        table = QTableView()
        table.setAlternatingRowColors(True)
        
        src_names = [""] + [c["col_name"] for c in self.source_metadata]
        tgt_names = [c["col_name"] for c in self.target_metadata]
        
        # Build current mapping lookup
        current_map = {}
        for r in self.mapping_rules:
            if r.get("tgt_col"):
                current_map[r["tgt_col"].lower()] = r.get("src_col", "")
        
        # Create a simple model for editing
        class MappingEditModel(QAbstractTableModel):
            def __init__(self, tgt_cols, src_options, existing_map):
                super().__init__()
                self.tgt_cols = tgt_cols
                self.src_options = src_options
                self.selections = []
                for t in tgt_cols:
                    mapped_src = existing_map.get(t.lower(), "")
                    self.selections.append(mapped_src)
                    
            def rowCount(self, parent=QModelIndex()):
                return len(self.tgt_cols)
            def columnCount(self, parent=QModelIndex()):
                return 2
            def data(self, index, role=Qt.ItemDataRole.DisplayRole):
                if role == Qt.ItemDataRole.DisplayRole:
                    if index.column() == 0:
                        return self.tgt_cols[index.row()]
                    else:
                        return self.selections[index.row()]
                return None
            def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
                if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
                    return ["Target Column", "Source Column"][section]
                return None
            def flags(self, index):
                flags = super().flags(index)
                if index.column() == 1:
                    flags |= Qt.ItemFlag.ItemIsEditable
                return flags
            def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
                if index.column() == 1 and role == Qt.ItemDataRole.EditRole:
                    self.selections[index.row()] = value
                    self.dataChanged.emit(index, index)
                    return True
                return False
        
        model = MappingEditModel(tgt_names, src_names, current_map)
        table.setModel(model)
        
        # Use combo box delegates for source column selection
        from PySide6.QtWidgets import QStyledItemDelegate
        class ComboDelegate(QStyledItemDelegate):
            def __init__(self, options, parent=None):
                super().__init__(parent)
                self.options = options
            def createEditor(self, parent, option, index):
                combo = QComboBox(parent)
                combo.addItems(self.options)
                return combo
            def setEditorData(self, editor, index):
                val = index.model().data(index, Qt.ItemDataRole.DisplayRole)
                idx = editor.findText(val) if val else 0
                editor.setCurrentIndex(max(0, idx))
            def setModelData(self, editor, model, index):
                model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        
        delegate = ComboDelegate(src_names, table)
        table.setItemDelegateForColumn(1, delegate)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(table)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec():
            # Update mapping_rules from the editor
            new_rules = []
            for i, tgt in enumerate(tgt_names):
                src = model.selections[i]
                if src:
                    # Find existing rule to preserve rule_expr
                    old_rule = next((r for r in self.mapping_rules if r.get("tgt_col", "").lower() == tgt.lower()), None)
                    new_rules.append({
                        "src_col": src,
                        "src_type": old_rule.get("src_type", "VARCHAR") if old_rule else "VARCHAR",
                        "src_len": old_rule.get("src_len", "") if old_rule else "",
                        "tgt_col": tgt,
                        "rule_expr": old_rule.get("rule_expr", "") if old_rule else ""
                    })
            self.mapping_rules = new_rules
            self.refresh_grid()
            self.log_text.append(f"[SUCCESS] Saved {len(new_rules)} field mappings from editor.")
            self.status_bar.showMessage(f" ✅ {len(new_rules)} mappings saved.")

    def _build_code_config(self) -> CodeMappingConfig:
        """Builds a CodeMappingConfig from the parsed code_mappings dict."""
        config = CodeMappingConfig()
        for field_name, value_map in self.code_mappings.items():
            code_list = CodeMappingList(field_name)
            for src_val, tgt_val in value_map.items():
                code_list.add_mapping(str(src_val), str(tgt_val))
            config.add_list(code_list)
        return config

    def handle_code_mapping(self):
        self.log_text.append("[ACTION] 🔀 Applying Code Mappings...")
        if not self.code_mappings:
            QMessageBox.information(self, "Code Mapping", "No 'List Of Values' loaded. Please load an IDS Excel containing this sheet.")
            return
            
        code_config = self._build_code_config()
        total_rules = sum(len(v) for v in self.code_mappings.values())
        
        msg = f"Loaded {total_rules} value mappings across {len(self.code_mappings)} fields:\n\n"
        for field, mapping in self.code_mappings.items():
            preview = ", ".join(f"{k}→{v}" for k, v in list(mapping.items())[:3])
            if len(mapping) > 3:
                preview += f"... (+{len(mapping)-3} more)"
            msg += f"• {field}: {preview}\n"
        QMessageBox.information(self, "Code Mapping Configured", msg)
        self.log_text.append(f"[SUCCESS] Code mappings configured: {total_rules} rules across {len(self.code_mappings)} fields.")

    def handle_transformation(self):
        self.log_text.append("[ACTION] ⚙️ Running Transformations Engine...")
        if not self.mapping_rules or not self.source_metadata:
            QMessageBox.warning(self, "Warning", "Mapping rules and Source Schema must be loaded.")
            return
            
        try:
            # Build MappingDefinition
            mapping_def = MappingDefinition("Active", "Source", "Target")
            for r in self.mapping_rules:
                expr = r.get("rule_expr", "")
                is_expr = any(f in expr.lower() for f in ["concat(", "trim(", "uppercase(", "lowercase(", "name_first()", "name_middle()", "name_last()"])
                
                mapping_def.add_rule(FieldMappingRule(
                    target_col=r.get("tgt_col", ""),
                    source_col=r.get("src_col", ""),
                    mode="expression" if is_expr else "direct",
                    expression=expr
                ))
                
            # Wire real CodeMappingConfig from loaded code mappings
            code_config = self._build_code_config() if self.code_mappings else CodeMappingConfig()
            
            engine = TransformationEngine(mapping_def, code_config)
            
            # Use real data if loaded, else use mock data
            data_type_msg = "mock"
            if hasattr(self, 'source_data') and self.source_data is not None:
                source_df = self.source_data
                data_type_msg = "loaded"
                self.log_text.append(f"[INFO] Using {len(source_df)} rows of loaded source data.")
            else:
                # Create a mock source dataframe with 5 rows
                mock_data = {}
                for col in self.source_metadata:
                    mock_data[col["col_name"]] = [f"Mock_{col['col_name']}_{i}" for i in range(5)]
                source_df = pd.DataFrame(mock_data)
                self.log_text.append("[WARNING] No real source data loaded. Using 5 rows of mock data.")
            
            self.show_spinner()
            self.status_bar.showMessage(" Running Transformations (Please wait)...")
            
            self.transform_thread = TransformationThread(engine, source_df)
            
            # Store cm_msg in the thread object temporarily so we can use it in the callback
            self.transform_thread.cm_msg = f" (with {len(self.code_mappings)} code mapping fields)" if self.code_mappings else ""
            self.transform_thread.data_type_msg = data_type_msg
            
            self.transform_thread.finished.connect(self.on_transform_finished)
            self.transform_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Transformation Setup Error", f"Failed to start transformation:\n{e}")
            self.log_text.append(f"[ERROR] Transform error: {e}\n{traceback.format_exc()}")

    def on_transform_finished(self, staged_data, error):
        self.hide_spinner()
        if error:
            QMessageBox.critical(self, "Transformation Error", f"Transformation failed:\n{error}")
            self.log_text.append(f"[ERROR] Transform error:\n{error}")
            self.status_bar.showMessage(" ❌ Transformation failed.")
        else:
            self.staged_data = staged_data
            cm_msg = getattr(self.transform_thread, 'cm_msg', '')
            data_type_msg = getattr(self.transform_thread, 'data_type_msg', 'loaded')
            
            self.log_text.append(f"[INFO] Applied {len(self.mapping_rules)} transformations{cm_msg} on {data_type_msg} source data.")
            self.status_bar.showMessage(f" ✅ Generated {len(self.staged_data)} staged rows.")
            
            # Update Target Data Preview Tab
            from ui.widgets.mapping_grid_model import DataFrameModel
            model = DataFrameModel(self.staged_data)
            self.target_data_view.setModel(model)
            
            QMessageBox.information(self, "Transformations", f"Expressions parsed safely! Generated {len(self.staged_data)} staged rows.{cm_msg}\nYou can view it in the 'Data Previews' tab.")

    def handle_staging_preview(self):
        # We replaced this with the Data Previews Tab!
        self.tabs.setCurrentIndex(1)
        QMessageBox.information(self, "Data Preview", "The side-by-side data preview is now in the 'Data Previews' tab in the main area.")
        


    def handle_validation(self):
        self.log_text.append("[ACTION] ✅ Running Validation Engine against Target Schema...")
        if not self.target_metadata:
            QMessageBox.warning(self, "Warning", "Please load a Target Schema first to validate against.")
            return
            
        if self.staged_data is None:
            QMessageBox.warning(self, "Warning", "No staged data available. Run Transformation first.")
            return
            
        try:
            tgt_meta = [c["_meta"] for c in self.target_metadata if "_meta" in c]
            engine = ValidationEngine(tgt_meta)
            result = engine.validate(self.staged_data)
            
            self.val_text.clear()
            self.val_text.append("=== VALIDATION RESULTS ===\n")
            self.val_text.append(f"[INFO] Processed {result.total_rows} rows.")
            self.val_text.append(f"[INFO] Passed: {result.pass_count}, Failed: {result.fail_count}\n")
            
            if result.fail_count > 0:
                for failure in result.failure_reasons[:50]: # Show up to 50
                    self.val_text.append(f"Row {failure['row_index']} - {failure['column']}: {failure['reason']}")
                QMessageBox.warning(self, "Validation Failed", f"Validation found {result.fail_count} error rows! See Results tab.")
                self.log_text.append(f"[WARNING] Validation failed with {result.fail_count} errors.")
            else:
                self.val_text.append("Validation complete: 0 Error Rows found. Ready to Push!")
                QMessageBox.information(self, "Validation Passed", "Validation complete: 0 Error Rows found. Ready to Push!")
                self.log_text.append("[SUCCESS] Validation passed.")
        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Validation failed:\n{e}")
            self.log_text.append(f"[ERROR] Validation error: {e}")

    def handle_export(self):
        if self.staged_data is None:
            QMessageBox.warning(self, "Warning", "No staged data to export. Run Transformation first.")
            return
            
        self.btn_deploy.setEnabled(False)
        self.status_bar.showMessage(" ⚙️ Exporting flat file in background...")
        
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Flat File", "output.csv", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)")
        if not filepath:
            self.btn_deploy.setEnabled(True)
            self.status_bar.showMessage(" Export Cancelled.")
            return
            
        self.log_text.append(f"[INFO] Starting secure export process to {filepath}...")
        
        def _export_task():
            import time
            time.sleep(1) # simulate work
            writer = FlatFileWriter(filepath)
            writer.write(self.staged_data)
            return f"Export successful: Data written to {filepath} (Pipe delimited)"
            
        self.worker_thread = WorkerThread(_export_task)
        self.worker_thread.result_ready.connect(self.on_export_success)
        self.worker_thread.error_occurred.connect(self.on_export_error)
        self.worker_thread.finished.connect(lambda: self.btn_deploy.setEnabled(True))
        self.worker_thread.start()

    def on_export_success(self, result):
        QMessageBox.information(self, "Export Complete", str(result))
        self.log_text.append(f"[SUCCESS] {result}")
        self.status_bar.showMessage(" ✅ Ready. Last run: Export successful.")

    def on_export_error(self, err_msg):
        QMessageBox.critical(self, "Export Error", err_msg)
        self.log_text.append(f"[ERROR] {err_msg}")
        self.status_bar.showMessage(" ❌ Ready. Last run: Export failed.")

    def handle_validation_source(self):
        self.log_text.append("[ACTION] 🧪 Validating Source Data...")
        QMessageBox.information(self, "Coming Soon", "Source Validation will run rules directly against the CBS_Staging_Source table.")

    def handle_find_gaps_source(self):
        self.log_text.append("[ACTION] 🔍 Finding Source Gaps...")
        QMessageBox.information(self, "Coming Soon", "Source Gap Analysis will check for missing mandatory fields in the CBS_Staging_Source table.")

    def handle_validation_target(self):
        self.log_text.append("[ACTION] 🧪 Validating Target Data...")
        self.handle_validation()

    def handle_find_gaps_target(self):
        self.log_text.append("[ACTION] 🔍 Finding Target Gaps...")
        self.handle_find_gaps()

    def handle_push_source_staging(self):
        self.log_text.append("[ACTION] 🚀 Pushing to Source Staging Table...")
        if self.source_data is None:
            QMessageBox.warning(self, "Warning", "Please load Source Data first.")
            return
            
        if not self.source_metadata:
            QMessageBox.warning(self, "Warning", "Please load Source Schema so we know which table to push to.")
            return
            
        table_name = self.source_metadata[0].get("table_name", "CBS_Staging_Source")
            
        dialog = ConnectionDialog(self)
        dialog.setWindowTitle(f"Connect to Staging Database (Table: {table_name})")
        if dialog.exec():
            conn_str, is_offline, ui_table_name = dialog.get_connection_details()
            if ui_table_name:
                table_name = ui_table_name
                
            if is_offline:
                QMessageBox.warning(self, "Warning", "Cannot push to an offline DDL script.")
                return
            
            self.show_spinner()
            self.status_bar.showMessage(f" Inserting data into {table_name} (Append Mode)...")
            
            self.push_src_thread = PushDataThread(self.source_data, conn_str, table_name, self.source_metadata)
            self.push_src_thread.finished.connect(self._on_push_finished)
            self.push_src_thread.start()

    def handle_push_target_staging(self):
        self.log_text.append("[ACTION] 🚀 Pushing to Target Staging Table...")
        if self.staged_data is None:
            QMessageBox.warning(self, "Warning", "Please run Transformation first.")
            return
            
        if not self.target_metadata:
            QMessageBox.warning(self, "Warning", "Please load Target Schema so we know which table to push to.")
            return
            
        table_name = self.target_metadata[0].get("table_name", "CBS_Staging_Target")
            
        dialog = ConnectionDialog(self)
        dialog.setWindowTitle(f"Connect to Staging Database (Table: {table_name})")
        if dialog.exec():
            conn_str, is_offline, ui_table_name = dialog.get_connection_details()
            if ui_table_name:
                table_name = ui_table_name
                
            if is_offline:
                QMessageBox.warning(self, "Warning", "Cannot push to an offline DDL script.")
                return
            
            self.show_spinner()
            self.status_bar.showMessage(f" Inserting data into {table_name} (Append Mode)...")
            
            self.push_tgt_thread = PushDataThread(self.staged_data, conn_str, table_name, self.target_metadata)
            self.push_tgt_thread.finished.connect(self._on_push_finished)
            self.push_tgt_thread.start()

    def _on_push_finished(self, msg, table_name, count):
        self.hide_spinner()
        if msg and not msg.strip().startswith("Warning:"):
            QMessageBox.critical(self, "Push Error", f"Failed to push to {table_name}:\n{msg}")
            self.log_text.append(f"[ERROR] DB Push failed for {table_name}:\n{msg}")
            self.status_bar.showMessage(f" ❌ Push failed for {table_name}.")
        else:
            QMessageBox.information(self, "Success", f"Successfully pushed {count} rows to {table_name}.{msg}")
            self.log_text.append(f"[SUCCESS] Pushed {count} rows to {table_name}.{msg}")
            self.status_bar.showMessage(" ✅ Push complete.")
