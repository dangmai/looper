#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QHeaderView, QTableView


class TimestampTableView(QTableView):
    def __init__(self, parent=None):
        super(TimestampTableView, self).__init__(parent)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def mouseReleaseEvent(self, event):
        super(TimestampTableView, self).mouseReleaseEvent(event)
        index = self.indexAt(event.pos())
        if not index.isValid():
            self.selectionModel().clearSelection()
