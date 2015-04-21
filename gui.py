#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Program to loop videos based on timestamps in a text file
"""

import argparse
import json
import os
import sys
import traceback
from datetime import timedelta

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, \
    QMessageBox, QFrame, QSlider, QStyle, QStyleOptionSlider, QHeaderView, \
    QTableView
from PyQt5.QtGui import QPalette, QColor, QWheelEvent, QKeyEvent, QPainter, \
    QPen
from PyQt5.QtCore import QTimer, pyqtSignal, Qt, QAbstractTableModel, QVariant, \
    QRect

import vlc


class TimestampDelta(timedelta):
    def __new__(cls, *args, **kwargs):
        return super(TimestampDelta, cls).__new__(cls, *args, **kwargs)

    def __str__(self):
        mm, ss = divmod(self.seconds, 60)
        hh, mm = divmod(mm, 60)
        if self.days:
            hh += self.days * 24
        ms, _ = divmod(self.microseconds, 1000)
        s = "%d:%02d:%02d.%03d" % (hh, mm, ss, ms)
        return s

    @property
    def milliseconds(self):
        ms = self.seconds * 1000000
        if self.microseconds:
            ms += self.microseconds
        if self.days:
            ms += self.days * 24 * 60 * 60 * 100000
        return int(ms/1000)


class Timestamp():
    def __init__(self, start_time, end_time, description=None):
        self.start_time = TimestampDelta(milliseconds=start_time)
        self.end_time = TimestampDelta(milliseconds=end_time)
        self.description = description

    def get_displayed_start_time(self):
        return str(self.start_time)

    def get_displayed_end_time(self):
        return str(self.end_time)

    def get_string_value_from_index(self, index):
        return str(self.start_time) if index == 0 else str(self.end_time) if index == 1\
            else self.description

    def get_value_from_index(self, index):
        return self.start_time if index == 0 else self.end_time if index == 1 \
            else self.description

    def __repr__(self):
        return json.dumps({
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "description": self.description
        })


class TimestampList():
    HEADERS = [
        "Start Time",
        "End Time",
        "Description"
    ]

    def __init__(self, data=[]):
        self.list = []
        for timestamp in data:
            self.list.append(
                Timestamp(
                    timestamp['start_time'],
                    timestamp['end_time'],
                    timestamp['description']
                )
            )

    def append(self, timestamp):
        self.list.append(timestamp)

    def header_at_index(self, index):
        return TimestampList.HEADERS[index]

    def __len__(self):
        return len(self.list)

    def __getitem__(self, item):
        return self.list[item]

    def __str__(self):
        return str(self.list)

    def __repr__(self):
        return repr(self.list)


class TimestampModel(QAbstractTableModel):
    def __init__(self, input_file_location=None, parent=None):
        super(TimestampModel, self).__init__(parent)
        self.input_file_location = input_file_location
        self.list = TimestampList()

        if input_file_location:
            with open(self.input_file_location, "r+") as input_file:
                self.list = TimestampList(json.load(input_file))

    def rowCount(self, parent=None, *args, **kwargs):
        if parent and parent.isValid():
            return 0
        return len(self.list)

    def columnCount(self, parent=None, *args, **kwargs):
        if parent and parent.isValid():
            return 0
        return 3

    def data(self, index, role=None):
        if not index.isValid():
            return QVariant()
        if role == Qt.UserRole:
            return self.list[index.row()].get_value_from_index(index.column())
        if role != Qt.DisplayRole:
            return QVariant()
        return self.list[index.row()].get_string_value_from_index(
            index.column())

    def headerData(self, col, orientation, role=None):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.list.header_at_index(col)
        return QVariant()


class TimestampTableView(QTableView):
    def __init__(self, parent=None):
        super(TimestampTableView, self).__init__(parent)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def mouseReleaseEvent(self, event):
        super(TimestampTableView, self).mouseReleaseEvent(event)
        index = self.indexAt(event.pos())
        if not index.isValid():
            self.selectionModel().clearSelection()


class VideoFrame(QFrame):
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

    def set_highlight_start(self, highlight_start):
        self.highlight_start = highlight_start \
            if self.highlight_end is None or \
            highlight_start < self.highlight_end else None

    def set_highlight_end(self, highlight_end):
        self.highlight_end = highlight_end \
            if self.highlight_start is None or \
            highlight_end > self.highlight_start else None

    def paintEvent(self, event):
        if self.highlight_start and self.highlight_end:
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
            p.drawRects(QRect(start_x, start_y, width, height))
        super(HighlightedJumpSlider, self).paintEvent(event)


class MainWindow(QMainWindow):
    """
    The main window class
    """
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.ui = uic.loadUi("main_window.ui")

        self.timestamp_filename = None
        self.video_filename = None
        self.media_start_time = None
        self.media_end_time = None
        self.restart_needed = False
        self.timer_period = 100
        self.is_full_screen = False
        self.media_started_playing = False
        self.original_window_flags = None

        self.ui.list_timestamp.setModel(TimestampModel(None, self))

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.timeout.connect(self.timer_handler)
        self.timer.start(self.timer_period)

        self.ui.button_run.clicked.connect(self.run)
        self.ui.button_timestamp_browse.clicked.connect(
            self.browse_timestamp_handler
        )
        self.ui.button_video_browse.clicked.connect(
            self.browse_video_handler
        )
        self.vlc_instance = vlc.Instance()
        self.media_player = self.vlc_instance.media_player_new()
        # if sys.platform == "darwin":  # for MacOS
        #     self.ui.frame_video = QMacCocoaViewContainer(0)
        self.ui.frame_video.double_clicked.connect(self.toggle_full_screen)
        self.ui.frame_video.wheel.connect(self.wheel_handler)
        self.ui.frame_video.key_pressed.connect(self.key_handler)
        self.ui.button_play_pause.clicked.connect(self.play_pause)
        self.ui.button_full_screen.clicked.connect(self.toggle_full_screen)
        self.ui.button_speed_up.clicked.connect(self.speed_up_handler)
        self.ui.button_slow_down.clicked.connect(self.slow_down_handler)
        self.ui.button_mute_toggle.clicked.connect(self.toggle_mute)
        self.ui.slider_progress.setTracking(False)
        self.ui.slider_progress.valueChanged.connect(self.set_media_position)
        self.ui.slider_volume.valueChanged.connect(self.set_volume)
        # Set up default volume
        self.set_volume(self.ui.slider_volume.value())
        self.vlc_events = self.media_player.event_manager()
        self.vlc_events.event_attach(
            vlc.EventType.MediaPlayerTimeChanged, self.media_time_change_handler
        )
        self.media_player.video_set_mouse_input(False)
        self.media_player.video_set_key_input(False)
        self.ui.show()

    def set_media_position(self, position):
        self.media_player.set_position(position / 10000.0)
        self.media_end_time = -1

    def update_ui(self):
        self.ui.slider_progress.blockSignals(True)
        self.ui.slider_progress.setValue(
            self.media_player.get_position() * 10000
        )
        self.ui.slider_progress.blockSignals(False)

    def timer_handler(self):
        """
        This is a workaround, because for some reason we can't call set_time()
        inside the MediaPlayerTimeChanged handler (as the video just stops
        playing)
        """
        if self.restart_needed:
            self.media_player.set_time(self.media_start_time)
            self.restart_needed = False

    def key_handler(self, event):
        if event.key() == Qt.Key_Escape and self.is_full_screen:
            self.toggle_full_screen()
        if event.key() == Qt.Key_F:
            self.toggle_full_screen()

    def wheel_handler(self, event):
        self.modify_volume(1 if event.angleDelta().y() > 0 else -1)

    def toggle_mute(self):
        self.media_player.audio_set_mute(not self.media_player.audio_get_mute())

    def modify_volume(self, delta_percent):
        new_volume = self.media_player.audio_get_volume() + delta_percent
        if new_volume < 0:
            new_volume = 0
        elif new_volume > 40:
            new_volume = 40
        self.media_player.audio_set_volume(new_volume)
        self.ui.slider_volume.setValue(self.media_player.audio_get_volume())

    def set_volume(self, new_volume):
        self.media_player.audio_set_volume(new_volume)

    def speed_up_handler(self):
        self.modify_rate(0.1)

    def slow_down_handler(self):
        self.modify_rate(-0.1)

    def modify_rate(self, delta_percent):
        new_rate = self.media_player.get_rate() + delta_percent
        if new_rate < 0.2 or new_rate > 2.0:
            return
        self.media_player.set_rate(new_rate)

    def media_time_change_handler(self, _):
        if self.media_end_time == -1:
            return
        if self.media_player.get_time() > self.media_end_time:
            self.restart_needed = True

    def run(self):
        """
        Execute the loop
        """
        if self.timestamp_filename is None:
            self._show_error("No timestamp file chosen")
            return
        if self.video_filename is None:
            self._show_error("No video file chosen")
            return
        try:
            if self.ui.list_timestamp.selectionModel().hasSelection():
                selected_row = self.ui.list_timestamp.selectionModel().\
                    selectedRows()[0]
                start_delta = self.ui.list_timestamp.model().data(
                    selected_row.model().index(selected_row.row(), 0),
                    Qt.UserRole
                )
                end_delta = self.ui.list_timestamp.model().data(
                    selected_row.model().index(selected_row.row(), 1),
                    Qt.UserRole
                )
                duration = self.media_player.get_media().get_duration()
                self.media_start_time = start_delta.milliseconds
                self.media_end_time = end_delta.milliseconds
                slider_start_pos = (self.media_start_time / duration) * (self.ui.slider_progress.maximum() - self.ui.slider_progress.minimum())
                slider_end_pos = (self.media_end_time / duration) * (self.ui.slider_progress.maximum() - self.ui.slider_progress.minimum())
                self.ui.slider_progress.set_highlight_start(int(slider_start_pos))
                self.ui.slider_progress.set_highlight_end(int(slider_end_pos))

            else:
                self.media_start_time = 0
                self.media_end_time = -1
            self.media_player.play()
            self.media_player.set_time(self.media_start_time)
            self.media_started_playing = True
        except Exception as ex:
            self._show_error(str(ex))
            print(traceback.format_exc())

    def play_pause(self):
        """Toggle play/pause status
        """
        if not self.media_started_playing:
            self.run()
            return
        if self.media_player.is_playing():
            self.media_player.pause()
        else:
            self.media_player.play()

    def toggle_full_screen(self):
        if self.is_full_screen:
            self.ui.frame_media.showNormal()
            self.ui.frame_media.setParent(self.ui.widget_central)
            self.ui.frame_media.resize(self.original_size)
            self.ui.frame_media.overrideWindowFlags(self.original_window_flags)
            self.ui.layout_main.addWidget(self.ui.frame_media, 2, 3, 1, 1)
            self.ui.frame_media.show()
        else:
            self.original_window_flags = self.ui.frame_media.windowFlags()
            self.original_size = self.ui.frame_media.size()
            self.ui.frame_media.setParent(None)
            self.ui.frame_media.setWindowFlags(Qt.FramelessWindowHint |
                                               Qt.CustomizeWindowHint)
            self.ui.frame_media.showFullScreen()
            self.ui.frame_media.show()
        self.ui.frame_video.setFocus()
        self.is_full_screen = not self.is_full_screen

    def browse_timestamp_handler(self):
        """
        Handler when the timestamp browser button is clicked
        """
        tmp_name, _ = QFileDialog.getOpenFileName(
            self, "Choose Timestamp file", None,
            "Timestamp File (*.tmsp);;All Files (*)"
        )
        if not tmp_name:
            return
        self.set_timestamp_filename(tmp_name)

    def set_timestamp_filename(self, filename):
        """
        Set the timestamp file name
        """
        if not os.path.isfile(filename):
            self._show_error("Cannot access timestamp file " + filename)
            return
        self.timestamp_filename = filename
        self.ui.entry_timestamp.setText(self.timestamp_filename)

        self.ui.list_timestamp.setModel(
            TimestampModel(self.timestamp_filename, self)
        )

        directory = os.path.dirname(self.timestamp_filename)
        basename = os.path.basename(self.timestamp_filename)
        timestamp_name_without_ext = os.path.splitext(basename)[0]
        for file_in_dir in os.listdir(directory):
            current_filename = os.path.splitext(file_in_dir)[0]
            found_video = (current_filename == timestamp_name_without_ext and
                           file_in_dir != basename)
            if found_video:
                found_video_file = os.path.join(directory, file_in_dir)
                self.set_video_filename(found_video_file)
                break

    def set_video_filename(self, filename):
        """
        Set the video filename
        """
        if not os.path.isfile(filename):
            self._show_error("Cannot access video file " + filename)
            return

        self.video_filename = filename

        media = self.vlc_instance.media_new(self.video_filename)
        media.parse()
        if not media.get_duration():
            self._show_error("Cannot play this media file")
            self.media_player.set_media(None)
            self.video_filename = None
        else:
            self.media_player.set_media(media)
            if sys.platform.startswith('linux'): # for Linux using the X Server
                self.media_player.set_xwindow(self.ui.frame_video.winId())
            elif sys.platform == "win32": # for Windows
                self.media_player.set_hwnd(self.ui.frame_video.winId())
            elif sys.platform == "darwin": # for MacOS
                self.media_player.set_nsobject(self.ui.frame_video.winId())
            self.ui.entry_video.setText(self.video_filename)
            self.media_started_playing = False

    def browse_video_handler(self):
        """
        Handler when the video browse button is clicked
        """
        tmp_name, _ = QFileDialog.getOpenFileName(
            self, "Choose Video file", None,
            "All Files (*)"
        )
        if not tmp_name:
            return
        self.set_video_filename(tmp_name)

    def _show_error(self, message, title="Error"):
        QMessageBox.warning(self, title, message)


def main():
    """
    Main function for the program
    """
    parser = argparse.ArgumentParser(
        description="Loop a video between 2 points in time based on rules in "
                    "a text file."
    )
    parser.add_argument('timestamp_filename', metavar='F', nargs='?',
                        help='the location of the timestamp file')
    parser.add_argument('--video_filename', metavar='V',
                        help='the location of the video file')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    main_window = MainWindow()

    if args.timestamp_filename:
        timestamp_filename = os.path.abspath(args.timestamp_filename)
        main_window.set_timestamp_filename(timestamp_filename)
    if args.video_filename:
        video_filename = os.path.abspath(args.video_filename)
        main_window.set_video_filename(video_filename)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
