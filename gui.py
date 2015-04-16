#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Program to loop videos based on timestamps in a text file
"""

import argparse
import os
import sys
import traceback

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, \
    QMessageBox, QTreeWidgetItem, QFrame
from PyQt5.QtGui import QPalette, QColor, QWheelEvent
from PyQt5.QtCore import QTimer, pyqtSignal, Qt

import loop
import vlc


class VideoFrame(QFrame):
    double_clicked = pyqtSignal()
    wheel = pyqtSignal(QWheelEvent)

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
        self.timer_period = 500
        self.is_full_screen = False
        self.media_played = False

        self.timer = QTimer()
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
        self.ui.frame_video.double_clicked.connect(self.toggle_fullscreen)
        self.ui.frame_video.wheel.connect(self.wheel_handler)
        self.ui.button_play_pause.clicked.connect(self.play_pause)
        self.ui.button_full_screen.clicked.connect(self.toggle_fullscreen)
        self.vlc_events = self.media_player.event_manager()
        self.vlc_events.event_attach(
            vlc.EventType.MediaPlayerTimeChanged, self.media_time_change_handler
        )
        self.ui.show()

    def timer_handler(self):
        """
        This is a workaround, because for some reason we can't call set_time()
        inside the MediaPlayerTimeChanged handler (as the video just stops
        playing)
        """
        if self.restart_needed:
            self.media_player.set_time(self.media_start_time)
            self.restart_needed = False

    def wheel_handler(self, event):
        self.modify_volume(1 if event.angleDelta().y() > 0 else -1)

    def modify_volume(self, delta_percent):
        new_volume = self.media_player.audio_get_volume() + delta_percent
        if new_volume < 0:
            new_volume = 0
        elif new_volume > 30:
            new_volume = 30
        self.media_player.audio_set_volume(new_volume)

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
        selected_timestamps = self.ui.list_timestamp.selectedItems()
        try:
            self.media = self.vlc_instance.media_new(self.video_filename)
            self.media_player.set_media(self.media)
            if sys.platform.startswith('linux'): # for Linux using the X Server
                self.media_player.set_xwindow(self.ui.frame_video.winId())
            elif sys.platform == "win32": # for Windows
                self.media_player.set_hwnd(self.ui.frame_video.winId())
            elif sys.platform == "darwin": # for MacOS
                self.media_player.set_nsobject(self.ui.frame_video.winId())
            if selected_timestamps:
                start_delta, end_delta = loop.parse_line_in_timestamp_file(
                    self.timestamp_filename, int(selected_timestamps[0].text(0))
                )
                self.media_start_time = start_delta.seconds * 1000
                self.media_end_time = end_delta.seconds * 1000
            else:
                self.media_start_time = 0
                self.media_end_time = -1
            self.media_player.play()
            self.media_player.set_time(self.media_start_time)
            self.media_played = True
        except Exception as ex:
            self._show_error(str(ex))
            print(traceback.format_exc())

    def play_pause(self):
        """Toggle play/pause status
        """
        if not self.media_played:
            self.run()
            return
        if self.media_player.is_playing():
            self.media_player.pause()
        else:
            self.media_player.play()

    def toggle_fullscreen(self):
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
            self.ui.frame_media.setWindowFlags(Qt.FramelessWindowHint | Qt.CustomizeWindowHint)
            self.ui.frame_media.showFullScreen()
            self.ui.frame_media.show()
        self.is_full_screen = not self.is_full_screen

    def set_fullscreen(self, mode = False):
        old_mode = self.media_player.get_fullscreen()
        new_mode = int(mode)

        self.media_player.set_fullscreen(new_mode)

        if new_mode:
            # New frame for fullscreen
            full = QFrame()
            self.media_player.set_xwindow(full.winId())
        else:
            self.media_player.set_xwindow(self.ui.frame_video.winId())

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

        for _ in range(self.ui.list_timestamp.topLevelItemCount()):
            self.ui.list_timestamp.takeTopLevelItem(0)
        with open(self.timestamp_filename, 'r') as timestamp_file:
            for index, line in enumerate(timestamp_file):
                start_delta, end_delta, description = loop.parse_line(line)
                timestamp = QTreeWidgetItem()
                timestamp.setText(0, str(index + 1))
                timestamp.setText(1, str(start_delta))
                timestamp.setText(2, str(end_delta))
                timestamp.setText(3, description)
                self.ui.list_timestamp.addTopLevelItem(timestamp)

        directory = os.path.dirname(self.timestamp_filename)
        basename = os.path.basename(self.timestamp_filename)
        name_without_ext = os.path.splitext(basename)[0]
        for file_in_dir in os.listdir(directory):
            if os.path.splitext(file_in_dir)[0] == name_without_ext and file_in_dir != basename:
                found_video_file = os.path.join(directory, file_in_dir)
                self.video_filename = found_video_file
                self.ui.entry_video.setText(self.video_filename)
                break

    def set_timestamp_num(self, num):
        """
        Set the chosen timestamp
        """
        if num > self.ui.list_timestamp.topLevelItemCount() or num < 0:
            self._show_error("Cannot select timestamp #" + str(num))
            return
        self.ui.list_timestamp.setCurrentItem(
            self.ui.list_timestamp.topLevelItem(num - 1)
        )

    def set_video_filename(self, filename):
        """
        Set the video filename
        """
        if not os.path.isfile(filename):
            self._show_error("Cannot access video file " + filename)
            return
        self.video_filename = filename
        self.ui.entry_video.setText(self.video_filename)
        self.media_played = False

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
    parser.add_argument('--timestamp_num', metavar='N', type=int,
                        help='which timestamp to use')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    main_window = MainWindow()

    if args.timestamp_filename:
        timestamp_filename = os.path.abspath(args.timestamp_filename)
        main_window.set_timestamp_filename(timestamp_filename)
        if args.timestamp_num:
            main_window.set_timestamp_num(args.timestamp_num)
    if args.video_filename:
        video_filename = os.path.abspath(args.video_filename)
        main_window.set_video_filename(video_filename)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
