"""
Mapping Grid Model.
A custom QAbstractTableModel to display source and target schema mappings efficiently.
"""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from typing import List, Dict, Any

class MappingGridModel(QAbstractTableModel):
    def __init__(self, mapping_data: List[Dict[str, Any]] = None):
        super().__init__()
        # Each dict in mapping_data contains source/target details
        self._data = mapping_data or []
        self.headers = [
            "Src Table", "Source Col", "Src Type", "Src Len", "Src Null",
            "Map Status",
            "Target Col", "Tgt Type", "Tgt Len", "Tgt Null", "Rule/Expr"
        ]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        row_data = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return row_data.get("src_table", "")
            elif col == 1: return row_data.get("src_col", "")
            elif col == 2: return row_data.get("src_type", "")
            elif col == 3: return str(row_data.get("src_len", ""))
            elif col == 4: return "Yes" if row_data.get("src_null") else "No"
            
            elif col == 5: return row_data.get("map_status", "🔴 Gap")
            
            elif col == 6: return row_data.get("tgt_col", "")
            elif col == 7: return row_data.get("tgt_type", "")
            elif col == 8: return str(row_data.get("tgt_len", ""))
            elif col == 9: return "Yes" if row_data.get("tgt_null") else "No"
            elif col == 10: return row_data.get("rule_expr", "")
            
        elif role == Qt.ItemDataRole.EditRole:
            if col == 1: return row_data.get("src_col", "")
            
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in [3, 8]: # lengths
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

    def flags(self, index):
        default_flags = super().flags(index)
        if index.column() == 1:  # Source Col is editable
            return default_flags | Qt.ItemFlag.ItemIsEditable
        return default_flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.column() == 1 and role == Qt.ItemDataRole.EditRole:
            self._data[index.row()]["src_col"] = value
            self.dataChanged.emit(index, index)
            return True
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_data: List[Dict[str, Any]]):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
