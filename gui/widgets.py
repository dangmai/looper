#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QFrame, QSlider, QStyle, QStyleOptionSlider, \
    QPlainTextEdit, QPushButton
from PyQt5.QtGui import QPalette, QColor, QWheelEvent, QKeyEvent, QPainter, \
    QPen
from PyQt5.QtCore import pyqtSignal, QRect


class VideoFrame(QFrame):
    """
    A frame used specifically for video/media purpose
    """
    double_clicked = pyqtSignal()
    wheel = pyqtSignal(QWheelEvent)
    key_pressed = pyqtSignal(QKeyEvent)

    def __init__(self, parent=None):
        QFrame.__init__(self, parent)

        self.original_parent = parent
        self.palette = self.palette()
        self.palette.setColor(QPalette.Window, QColor(0,0,0))

        self.setPalette(self.palette)
        self.setAutoFillBackground(True)

    def mouseDoubleClickEvent(self, _):
        self.double_clicked.emit()

    def wheelEvent(self, event):
        self.wheel.emit(event)

    def keyPressEvent(self, event):
        self.key_pressed.emit(event)


class HighlightedJumpSlider(QSlider):
    """
    Slider that allows user to jump to any point on it, regardless of steps.
    It also supports partial highlighting.
    """
    def __init__(self, parent=None):
        super(HighlightedJumpSlider, self).__init__(parent)
        self.highlight_start = None
        self.highlight_end = None

    def mousePressEvent(self, ev):
        """ Jump to click position """
        self.setValue(QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), ev.x(), self.width())
        )

    def mouseMoveEvent(self, ev):
        """ Jump to pointer position while moving """
        self.setValue(QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), ev.x(), self.width())
        )

    def set_highlight(self, start, end):
        if start is not None and end is not None and start < end:
            self.highlight_start, self.highlight_end = start, end

    def paintEvent(self, event):
        if self.highlight_start is not None and self.highlight_end is not None:
            p = QPainter(self)
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            gr = self.style().subControlRect(QStyle.CC_Slider, opt,
                                             QStyle.SC_SliderGroove, self)
            rect_x, rect_y, rect_w, rect_h = gr.getRect()
            start_x = int(
                (rect_w/(self.maximum() - self.minimum()))
                * self.highlight_start + rect_x
            )
            start_y = rect_y + 3
            width = int(
                (rect_w/(self.maximum() - self.minimum()))
                * self.highlight_end + rect_x
            ) - start_x
            height = rect_h - 3
            c = QColor(0, 152, 116)
            p.setBrush(c)
            c.setAlphaF(0.3)
            p.setPen(QPen(c, 1.0))
            rect_to_paint = QRect(start_x, start_y, width, height)
            p.drawRects(rect_to_paint)
        super(HighlightedJumpSlider, self).paintEvent(event)


class PlainTextEdit(QPlainTextEdit):
    """
    For some reason Qt refuses to style readOnly QPlainTextEdit correctly, so
    this class is a workaround for that
    """
    def setReadOnly(self, read_only):
        super(PlainTextEdit, self).setReadOnly(read_only)
        if read_only:
            self.setStyleSheet("QPlainTextEdit {"
                               "background-color: #F0F0F0;"
                               "color: #808080;"
                               "border: 1px solid #B0B0B0;"
                               "border-radius: 2px;"
                               "}")
        elif not read_only:
            self.setStyleSheet("QPlainTextEdit {"
                               "background-color: #FFFFFF;"
                               "color: #000000;"
                               "border: 1px solid #B0B0B0;"
                               "border-radius: 2px;"
                               "}")


class ToggleButton(QPushButton):
    """
    This is a QPushButton that supports toggling. It can have two states: True
    or False, each has its own set of text and icon. The button is controlled
    by a ToggleButtonModel. Without a model, the button behaves exactly like
    a QPushButton
    """
    stateChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(ToggleButton, self).__init__(parent)
        self.model = None
        self.clicked.connect(self.toggle)

    def toggle(self):
        if not self.model:
            return
        self.model.setState(not self.model.getState())

    def _state_change_handler(self):
        if not self.model:
            return
        self.setText(self.model.getText(self.model.getState()))
        self.setIcon(self.model.getIcon(self.model.getState()))
        self.stateChanged.emit(self.model.getState())

    def setModel(self, model):
        """
        Use a model for this button. The model will notify this button when a
        new state is required
        :param model: The model to use
        :return: None
        """
        self.model = model
        self._state_change_handler()
        self.model.dataChanged.connect(self._state_change_handler)
        self.model.stateChanged.connect(self._state_change_handler)

