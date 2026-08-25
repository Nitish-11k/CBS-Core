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
    QDialog, QComboBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, QSize, QAbstractTableModel, QModelIndex
from ui.widgets.mapping_grid_model import MappingGridModel
from ui.workers.db_worker import WorkerThread
from ui.widgets.connection_dialog import ConnectionDialog
from core.mapping.ids_parser import IDSParser
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
        
        # Apply a sleek Dark Theme style
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
            QWidget { font-family: 'Segoe UI', Inter, sans-serif; }
            QGroupBox { font-weight: bold; border: 1px solid #45475a; border-radius: 6px; margin-top: 12px; color: #cdd6f4; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; color: #89b4fa; }
            QToolBar { background-color: #181825; border-bottom: 1px solid #313244; spacing: 8px; padding: 5px; }
            QToolBar QToolButton { padding: 6px 12px; border-radius: 4px; background: #313244; color: #cdd6f4; font-weight: 500; }
            QToolBar QToolButton:hover { background: #89b4fa; color: #1e1e2e; }
            QTableView { border: 1px solid #313244; gridline-color: #45475a; background-color: #181825; color: #cdd6f4; alternate-background-color: #1e1e2e; selection-background-color: #89b4fa; selection-color: #1e1e2e; }
            QHeaderView::section { background-color: #313244; color: #cdd6f4; padding: 6px; font-weight: bold; border: none; border-right: 1px solid #45475a; }
            QPushButton { background-color: #89b4fa; color: #1e1e2e; border: none; padding: 6px 15px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #b4befe; }
            QTextEdit { background-color: #181825; color: #a6e3a1; border: 1px solid #313244; border-radius: 4px; font-family: Consolas, monospace; }
            QLabel { color: #cdd6f4; }
            QTabBar::tab { background: #313244; color: #cdd6f4; padding: 8px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #181825; border-top: 2px solid #89b4fa; }
        """)
        
        self.worker_thread = None
        
        # State Management
        self.source_metadata = []
        self.target_metadata = []
        self.mapping_rules = []
        self.code_mappings = {}
        self.staged_data = None
        self.source_data = None
        
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 1. Top Information Panel (Data Sources)
        info_group = QGroupBox("🔗 Data Sources")
        info_layout = QHBoxLayout(info_group)
        
        self.btn_load_source = QPushButton("📂 Load Source Schema")
        self.btn_load_target = QPushButton("🎯 Load Target Schema")
        self.btn_load_mapping = QPushButton("📑 Load IDS Mapping")
        self.btn_load_data = QPushButton("📥 Load Source Data (Live)")
        
        self.lbl_source = QLabel("Source: Not Loaded")
        self.lbl_target = QLabel("Target: Not Loaded")
        self.lbl_mapping = QLabel("Mapping: Not Loaded")
        self.lbl_data = QLabel("Data: Mock")
        
        info_layout.addWidget(self.btn_load_source)
        info_layout.addWidget(self.lbl_source)
        info_layout.addSpacing(20)
        info_layout.addWidget(self.btn_load_target)
        info_layout.addWidget(self.lbl_target)
        info_layout.addSpacing(20)
        info_layout.addWidget(self.btn_load_mapping)
        info_layout.addWidget(self.lbl_mapping)
        info_layout.addSpacing(20)
        info_layout.addWidget(self.btn_load_data)
        info_layout.addWidget(self.lbl_data)
        info_layout.addStretch()
        
        main_layout.addWidget(info_group)
        
        self.btn_load_source.clicked.connect(self.load_source_schema)
        self.btn_load_target.clicked.connect(self.load_target_schema)
        self.btn_load_mapping.clicked.connect(self.load_ids_mapping)
        self.btn_load_data.clicked.connect(self.load_source_data)

        # 2. Main Toolbar (Modes)
        toolbar = QToolBar("Action Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
        self.btn_gaps = toolbar.addAction("🔍 1. Find Gaps")
        self.btn_map = toolbar.addAction("🔗 2. Field Mapping")
        self.btn_code = toolbar.addAction("🔀 3. Code Mapping")
        self.btn_transform = toolbar.addAction("⚙️ 4. Transformation")
        self.btn_stage = toolbar.addAction("👁️ 5. Staging Preview")
        self.btn_validate = toolbar.addAction("✅ 6. Validation")
        
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
        legend = QLabel("Legend: 🟢 Mapped | 🟡 Unmapped Source (may be dropped) | 🔴 Target Gap (must map)")
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
        self.status_bar.setStyleSheet("background-color: #0097e6; color: white; font-weight: bold;")
        self.status_bar.showMessage(" Ready. Waiting for user action.")
        
        self.adjust_table_columns()

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
            if col == 1:
                # Update mapping rules
                new_src = self.table_model._data[row]["src_col"]
                tgt = self.table_model._data[row]["tgt_col"]
                
                rule_found = False
                for r in self.mapping_rules:
                    if r.get("tgt_col", "").lower() == tgt.lower():
                        r["src_col"] = new_src
                        rule_found = True
                        break
                        
                if not rule_found and tgt:
                    self.mapping_rules.append({
                        "src_col": new_src,
                        "tgt_col": tgt,
                        "rule_expr": ""
                    })
                
                # Refresh to re-evaluate statuses
                self.refresh_grid()

    def get_schema_from_dialog(self, source_type: str):
        dialog = ConnectionDialog(self)
        dialog.setWindowTitle(f"🔗 Load {source_type} Schema")
        if not dialog.exec():
            return None, None
            
        conn_str, is_offline = dialog.get_connection_details()
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
            
        conn_str, is_offline = dialog.get_connection_details()
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
                
            from PySide6.QtWidgets import QInputDialog
            table_name, ok = QInputDialog.getItem(self, "Select Table", "Choose table to load data from (TOP 1000):", available_tables, 0, False)
            if not ok or not table_name:
                return
                
            self.status_bar.showMessage(" ⚙️ Loading data...")
            
            try:
                # Try MSSQL TOP syntax
                self.source_data = pd.read_sql(f"SELECT TOP 1000 * FROM [{table_name}]", engine)
            except Exception:
                # Fallback to standard SQL LIMIT
                self.source_data = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 1000", engine)
                
            self.lbl_data.setText(f"Data: {len(self.source_data)} rows")
            self.lbl_data.setStyleSheet("color: #44bd32; font-weight: bold;")
            self.log_text.append(f"[SUCCESS] Loaded {len(self.source_data)} rows from {table_name}.")
            self.status_bar.showMessage(" ✅ Data loaded.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{e}")
            self.log_text.append(f"[ERROR] Data load failed: {e}\n{traceback.format_exc()}")
            self.status_bar.showMessage(" ❌ Data load failed.")

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
            # We assume expression if it has complex logic, direct otherwise
            mode = "expression" if len(r.get("rule_expr", "")) > 10 else "direct"
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
                mapping_def.add_rule(FieldMappingRule(
                    target_col=r.get("tgt_col", ""),
                    source_col=r.get("src_col", ""),
                    mode="direct" if not r.get("rule_expr") else "expression",
                    expression=r.get("rule_expr", "")
                ))
                
            # Wire real CodeMappingConfig from loaded code mappings
            code_config = self._build_code_config() if self.code_mappings else CodeMappingConfig()
            
            engine = TransformationEngine(mapping_def, code_config)
            
            # Use real data if loaded, else use mock data
            if hasattr(self, 'source_data') and self.source_data is not None:
                source_df = self.source_data
                self.log_text.append(f"[INFO] Using {len(source_df)} rows of loaded source data.")
            else:
                # Create a mock source dataframe with 5 rows
                mock_data = {}
                for col in self.source_metadata:
                    mock_data[col["col_name"]] = [f"Mock_{col['col_name']}_{i}" for i in range(5)]
                source_df = pd.DataFrame(mock_data)
                self.log_text.append("[WARNING] No real source data loaded. Using 5 rows of mock data.")
            
            self.staged_data = engine.transform(source_df)
            
            cm_msg = f" (with {len(self.code_mappings)} code mapping fields)" if self.code_mappings else ""
            self.log_text.append(f"[INFO] Applied {len(self.mapping_rules)} transformations{cm_msg} on mock source data.")
            QMessageBox.information(self, "Transformations", f"Expressions parsed safely! Generated {len(self.staged_data)} staged rows.{cm_msg}\nReady for staging preview and validation.")
        except Exception as e:
            QMessageBox.critical(self, "Transformation Error", f"Transformation failed:\n{e}")
            self.log_text.append(f"[ERROR] Transform error: {e}\n{traceback.format_exc()}")

    def handle_staging_preview(self):
        """Shows the staged DataFrame in a real QTableView dialog."""
        self.log_text.append("[ACTION] 👁️ Generating Staging Preview...")
        
        if self.staged_data is None:
            QMessageBox.warning(self, "Warning", "No staged data available. Run Transformation (Step 4) first.")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"👁️ Staging Preview — {len(self.staged_data)} rows × {len(self.staged_data.columns)} columns")
        dialog.resize(1000, 500)
        layout = QVBoxLayout(dialog)
        
        info = QLabel(f"Showing {len(self.staged_data)} rows, {len(self.staged_data.columns)} columns from transformed staging data.")
        info.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(info)
        
        # Build a QAbstractTableModel from the pandas DataFrame
        class DataFrameModel(QAbstractTableModel):
            def __init__(self, df):
                super().__init__()
                self._df = df
            def rowCount(self, parent=QModelIndex()):
                return len(self._df)
            def columnCount(self, parent=QModelIndex()):
                return len(self._df.columns)
            def data(self, index, role=Qt.ItemDataRole.DisplayRole):
                if role == Qt.ItemDataRole.DisplayRole:
                    val = self._df.iloc[index.row(), index.column()]
                    return "" if pd.isna(val) else str(val)
                return None
            def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
                if role == Qt.ItemDataRole.DisplayRole:
                    if orientation == Qt.Orientation.Horizontal:
                        return str(self._df.columns[section])
                    else:
                        return str(section)
                return None
        
        table = QTableView()
        table.setAlternatingRowColors(True)
        model = DataFrameModel(self.staged_data)
        table.setModel(model)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setStyleSheet("QHeaderView::section { background-color: #2d3436; color: white; padding: 4px; font-weight: bold; }")
        layout.addWidget(table)
        
        btn_close = QPushButton("✔️ Close")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        
        dialog.exec()
        self.log_text.append(f"[INFO] Staging preview displayed: {len(self.staged_data)} rows.")

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
            
        self.btn_push.setEnabled(False)
        self.status_bar.showMessage(" ⚙️ Exporting flat file in background...")
        
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Flat File", "output.csv", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)")
        if not filepath:
            self.btn_push.setEnabled(True)
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
