# custom_widgets.py

from PyQt5.QtWidgets import QFrame, QWidget
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QPropertyAnimation, QPoint, QEasingCurve, pyqtProperty
from PyQt5.QtGui import (
    QPainter, QPen, QPalette, QColor, QLinearGradient, QBrush, QPainterPath, QFont
)
from PyQt5.Qt import QRect

class CircularProgress(QFrame):
    """
    A circular progress widget with a background ring and
    a foreground progress ring (value = 0..100).
    """
    def __init__(
        self,
        size=90,
        value=50,
        thickness=15,
        pg_color="#2196f3",
        bg_ring_color="#e0e0e0",
        parent=None
    ):
        super().__init__(parent)
        self.size = size
        self.value = value
        self.thickness = thickness
        self.pg_color = pg_color
        self.bg_ring_color = bg_ring_color
        self.setFixedSize(self.size, self.size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.parent():
            parent_palette = self.parent().palette()
        else:
            parent_palette = self.palette()
        bg_color = parent_palette.color(QPalette.Window)
        painter.fillRect(self.rect(), bg_color)

        center_x = self.width() / 2
        center_y = self.height() / 2
        painter.translate(center_x, center_y)
        painter.rotate(-90)

        radius = (min(self.width(), self.height()) - self.thickness) / 2
        arc_rect = QRectF(-radius, -radius, 2 * radius, 2 * radius)

        background_pen = QPen(QColor(self.bg_ring_color), self.thickness, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(background_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(arc_rect, 0, 360 * 16)

        progress_pen = QPen(QColor(self.pg_color), self.thickness, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(progress_pen)
        angle_span = int(360 * 16 * (self.value / 100.0))
        painter.drawArc(arc_rect, 0, angle_span)

    def setValue(self, val):
        self.value = max(0, min(100, val))
        self.update()

    def setProgressColor(self, color):
        self.pg_color = color
        self.update()

    def setBackgroundRingColor(self, color):
        self.bg_ring_color = color
        self.update()


class BarChartFrame(QFrame):
    """
    A bar chart widget with optional shadow and gradient fill for each bar.
    """
    def __init__(self, bars=None, parent=None):
        super().__init__(parent)
        self.bars = bars if bars is not None else [0.4, 0.8, 0.6, 0.9, 0.2]
        self.setMinimumHeight(180)
        self.gradient_start = QColor("#27ae60")
        self.gradient_end = QColor("#2ecc71")
        self.enable_shadow = True
        self.shadow_color = QColor(0, 0, 0, 50)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        parent_palette = self.parent().palette() if self.parent() else self.palette()
        bg_color = parent_palette.color(QPalette.Window)
        painter.fillRect(rect, bg_color)

        if not self.bars:
            return

        margin = 10
        usable_width = rect.width() - 2 * margin
        usable_height = rect.height() - 2 * margin
        bar_width = usable_width / (len(self.bars) * 2)
        spacing = bar_width
        x = margin + spacing

        for value in self.bars:
            bar_h = usable_height * float(value)
            bar_x = int(x)
            bar_y = int(rect.height() - margin - bar_h)
            bar_w = int(bar_width)
            bar_h_int = int(bar_h)

            if self.enable_shadow:
                painter.setPen(Qt.NoPen)
                painter.setBrush(self.shadow_color)
                shadow_offset = 2
                painter.drawRoundedRect(
                    bar_x + shadow_offset,
                    bar_y + shadow_offset,
                    bar_w,
                    bar_h_int,
                    4, 4
                )

            gradient = QLinearGradient(QPointF(bar_x, bar_y), QPointF(bar_x, bar_y + bar_h_int))
            gradient.setColorAt(0.0, self.gradient_start)
            gradient.setColorAt(1.0, self.gradient_end)
            painter.setBrush(gradient)

            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(
                bar_x, bar_y, bar_w, bar_h_int, 4, 4
            )
            x += bar_width + spacing

    def setBars(self, bar_values):
        self.bars = bar_values
        self.update()

    def setEnableShadow(self, enable):
        self.enable_shadow = enable
        self.update()

    def setGradientColors(self, start_color, end_color):
        self.gradient_start = QColor(start_color)
        self.gradient_end = QColor(end_color)
        self.update()


class SemiCircularGauge(QFrame):
    """
    A semi-circular gauge for values in [min_val, max_val],
    with a colored arc and numeric value.
    """
    def __init__(
        self,
        min_val=0,
        max_val=100,
        value=50,
        gauge_width=14,
        gradient_start="#6a1b9a",
        gradient_end="#ab47bc",
        bg_color="#e0e0e0",
        parent=None
    ):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self._value = value
        self.gauge_width = gauge_width
        self.gradient_start = gradient_start
        self.gradient_end = gradient_end
        self.bg_color = bg_color
        self.setFixedSize(120, 80)

    def setValue(self, val):
        self._value = max(self.min_val, min(self.max_val, val))
        self.update()

    def value(self):
        return self._value

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        w = rect.width()
        h = rect.height()

        if self.parent():
            parent_pal = self.parent().palette()
            bg_parent = parent_pal.color(QPalette.Window)
            painter.fillRect(rect, bg_parent)
        else:
            painter.fillRect(rect, Qt.white)

        diameter = min(w, h * 2)
        arc_x = (w - diameter) / 2
        arc_y = h - diameter
        arc_rect = QRectF(arc_x, arc_y, diameter, diameter)

        background_pen = QPen(QColor(self.bg_color), self.gauge_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(background_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(arc_rect, 180 * 16, 180 * 16)

        if (self.max_val - self.min_val) != 0:
            fraction = (self._value - self.min_val) / (self.max_val - self.min_val)
        else:
            fraction = 0
        angle_span = fraction * 180.0
        angle_span_qt = int(angle_span * 16)

        gradient = QLinearGradient()
        gradient.setStart(arc_rect.center().x(), arc_rect.bottom())
        gradient.setFinalStop(arc_rect.center().x(), arc_rect.top())
        gradient.setColorAt(0.0, QColor(self.gradient_start))
        gradient.setColorAt(1.0, QColor(self.gradient_end))

        value_pen = QPen(QBrush(gradient), self.gauge_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(value_pen)
        painter.drawArc(arc_rect, 180 * 16, angle_span_qt)

        painter.setPen(Qt.black)
        if self.theme_is_dark():
            painter.setPen(Qt.white)

        font = self.font()
        font.setBold(True)
        painter.setFont(font)

        val_str = f"{int(round(self._value))}%"
        text_rect = QRectF(0, 0, w, h / 2.0)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.AlignVCenter, val_str)

        painter.end()

    def theme_is_dark(self):
        if not self.parent():
            return False
        bg = self.parent().palette().color(QPalette.Window)
        brightness = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
        return (brightness < 128)


class NeedleGauge(QFrame):
    """
    A gauge with a partial arc and a numeric value in the center.
    """
    def __init__(
        self,
        min_val=0,
        max_val=100,
        value=50,
        angle_min=-120,
        angle_max=120,
        arc_width=8,
        needle_color="#3949AB",
        arc_color="#aaaaaa",
        fill_color="#42A5F5",
        scale_color="#c8c8c8",
        theme='dark',
        parent=None
    ):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self._value = value
        self.angle_min = angle_min
        self.angle_max = angle_max
        self.arc_width = arc_width
        self.needle_color = needle_color
        self.arc_color = arc_color
        self.fill_color = fill_color
        self.scale_color = scale_color
        self.theme = theme
        self.setFixedSize(160, 120)

    def setTheme(self, theme: str):
        self.theme = theme
        self.update()

    def setValue(self, val):
        clamped = max(self.min_val, min(self.max_val, val))
        self._value = clamped
        self.update()

    def value(self):
        return self._value

    def setScaleColor(self, color: str):
        self.scale_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.parent():
            bg_color = self.parent().palette().color(QPalette.Window)
            painter.fillRect(self.rect(), bg_color)
        else:
            painter.fillRect(self.rect(), Qt.white)

        w, h = self.width(), self.height()
        margin = 10
        gauge_w = w - 2 * margin
        gauge_h = h - 2 * margin
        size = min(gauge_w, gauge_h)
        cx = self.rect().center().x()
        cy = self.rect().center().y()
        gauge_rect = QRectF(cx - size / 2, cy - size / 2, size, size)

        pen_bg = QPen(QColor(self.arc_color), self.arc_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_bg)
        painter.setBrush(Qt.NoBrush)
        start_angle = -self.angle_min
        span_angle = -(self.angle_max - self.angle_min)
        painter.drawArc(gauge_rect, int(start_angle * 16), int(span_angle * 16))

        if (self.max_val - self.min_val) != 0:
            fraction = (self._value - self.min_val) / (self.max_val - self.min_val)
        else:
            fraction = 0
        angle_for_value = self.angle_min + fraction * (self.angle_max - self.angle_min)
        start_angle_fill = -self.angle_min
        span_angle_fill = -(angle_for_value - self.angle_min)

        pen_fill = QPen(QColor(self.fill_color), self.arc_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_fill)
        painter.drawArc(gauge_rect, int(start_angle_fill * 16), int(span_angle_fill * 16))

        if self.theme == 'light':
            painter.setPen(Qt.black)
        else:
            painter.setPen(Qt.white)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        painter.setFont(font)

        val_str = f"{int(round(self._value))}"
        painter.drawText(gauge_rect, Qt.AlignCenter, val_str)

        painter.end()


class ToggleSwitch(QWidget):
    """
    A toggle switch widget with a sliding circle.
    Emits `toggled(bool)` on user interaction.
    """
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self._checked = checked
        self._circle_offset = 3 if not self._checked else 33
        self._anim = QPropertyAnimation(self, b"circle_offset", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.setFixedSize(60, 30)

        self._bg_on = QColor("#00bcd4")
        self._bg_off = QColor("#cccccc")
        self._circle = QColor("#ffffff")
        self._pen_off = QColor("#999999")

    @pyqtProperty(int)
    def circle_offset(self):
        return self._circle_offset

    @circle_offset.setter
    def circle_offset(self, pos):
        self._circle_offset = pos
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        radius = self.height() / 2
        rect = QRect(0, 0, self.width(), self.height())

        if self._checked:
            p.setBrush(QBrush(self._bg_on))
        else:
            p.setBrush(QBrush(self._bg_off))

        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, radius, radius)

        circle_rect = QRect(self._circle_offset, 3, self.height() - 6, self.height() - 6)
        p.setBrush(QBrush(self._circle))
        if not self._checked:
            pen = QPen(self._pen_off, 1)
            p.setPen(pen)
        else:
            p.setPen(Qt.NoPen)
        p.drawEllipse(circle_rect)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            start = self._circle_offset
            end = 33 if self._checked else 3
            self._anim.stop()
            self._anim.setStartValue(start)
            self._anim.setEndValue(end)
            self._anim.start()
            self.toggled.emit(self._checked)

    def isChecked(self):
        return self._checked

    def setChecked(self, state: bool):
        self._checked = state
        self._circle_offset = 33 if state else 3
        self.update()
