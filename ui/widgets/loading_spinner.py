import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen

class LoadingSpinner(QWidget):
    def __init__(self, parent=None, size=50, arc_color="#000000", bg_color="#e0e0e0"):
        super().__init__(parent)
        self.angle = 0
        self.arc_color = QColor(arc_color)
        self.bg_color = QColor(bg_color)
        self.spinner_size = size
        
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        # We only start the timer when shown to save resources
        
    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start(30) # ~33fps
        
    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()
        
    def rotate(self):
        self.angle = (self.angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        thickness = max(2, self.spinner_size // 10)
        rect_size = self.spinner_size - thickness
        
        # Draw background circle
        bg_pen = QPen(self.bg_color)
        bg_pen.setWidth(thickness)
        painter.setPen(bg_pen)
        painter.drawEllipse(thickness // 2, thickness // 2, rect_size, rect_size)
        
        # Draw rotating arc
        arc_pen = QPen(self.arc_color)
        arc_pen.setWidth(thickness)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        
        # drawArc uses 1/16th of a degree
        painter.drawArc(thickness // 2, thickness // 2, rect_size, rect_size, -self.angle * 16, 90 * 16)
