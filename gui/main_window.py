#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import traceback

import qtawesome as qta
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, \
    QMessageBox, QDataWidgetMapper
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import QDir, QTimer, Qt, QModelIndex

from lib import vlc
from app.model import TimestampModel, ToggleButtonModel


class MainWindow(QMainWindow):
    """
    The main window class
    """
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.ui = uic.loadUi("gui/main_window.ui")

        self.timestamp_filename = None
        self.video_filename = None
        self.media_start_time = None
        self.media_end_time = None
        self.restart_needed = False
        self.timer_period = 100
        self.is_full_screen = False
        self.media_started_playing = False
        self.media_is_playing = False
        self.original_geometry = None
        self.mute = False

        self.timestamp_model = TimestampModel(None, self)
        self.ui.list_timestamp.setModel(self.timestamp_model)
        self.ui.list_timestamp.doubleClicked.connect(
            lambda event: self.ui.list_timestamp.indexAt(event.pos()).isValid()
            and self.run()
        )

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.timeout.connect(self.timer_handler)
        self.timer.start(self.timer_period)

        self.vlc_instance = vlc.Instance()
        self.media_player = self.vlc_instance.media_player_new()
        # if sys.platform == "darwin":  # for MacOS
        #     self.ui.frame_video = QMacCocoaViewContainer(0)

        self.ui.frame_video.double_clicked.connect(self.toggle_full_screen)
        self.ui.frame_video.wheel.connect(self.wheel_handler)
        self.ui.frame_video.key_pressed.connect(self.key_handler)

        # Set up buttons
        self.ui.button_run.clicked.connect(self.run)
        self.ui.button_timestamp_browse.clicked.connect(
            self.browse_timestamp_handler
        )
        self.ui.button_video_browse.clicked.connect(
            self.browse_video_handler
        )

        self.play_pause_model = ToggleButtonModel(None, self)
        self.play_pause_model.setStateMap(
            {
                True: {
                    "text": "",
                    "icon": qta.icon("fa.play", scale_factor=0.7)
                },
                False: {
                    "text": "",
                    "icon": qta.icon("fa.pause", scale_factor=0.7)
                }
            }
        )
        self.ui.button_play_pause.setModel(self.play_pause_model)
        self.ui.button_play_pause.clicked.connect(self.play_pause)

        self.mute_model = ToggleButtonModel(None, self)
        self.mute_model.setStateMap(
            {
                True: {
                    "text": "",
                    "icon": qta.icon("fa.volume-up", scale_factor=0.8)
                },
                False: {
                    "text": "",
                    "icon": qta.icon("fa.volume-off", scale_factor=0.8)
                }
            }
        )
        self.ui.button_mute_toggle.setModel(self.mute_model)
        self.ui.button_mute_toggle.clicked.connect(self.toggle_mute)

        self.ui.button_full_screen.setIcon(
            qta.icon("ei.fullscreen", scale_factor=0.6)
        )
        self.ui.button_full_screen.setText("")
        self.ui.button_full_screen.clicked.connect(self.toggle_full_screen)
        self.ui.button_speed_up.clicked.connect(self.speed_up_handler)
        self.ui.button_speed_up.setIcon(
            qta.icon("fa.arrow-circle-o-up", scale_factor=0.8)
        )
        self.ui.button_speed_up.setText("")
        self.ui.button_slow_down.clicked.connect(self.slow_down_handler)
        self.ui.button_slow_down.setIcon(
            qta.icon("fa.arrow-circle-o-down", scale_factor=0.8)
        )
        self.ui.button_slow_down.setText("")
        self.ui.slider_progress.setTracking(False)
        self.ui.slider_progress.valueChanged.connect(self.set_media_position)
        self.ui.slider_volume.valueChanged.connect(self.set_volume)
        self.ui.entry_description.setReadOnly(True)

        # Mapper between the table and the entry detail
        self.mapper = QDataWidgetMapper()
        self.mapper.setSubmitPolicy(QDataWidgetMapper.ManualSubmit)
        self.mapper.setModel(self.timestamp_model)
        self.mapper.addMapping(self.ui.entry_start_time, 0)
        self.mapper.addMapping(self.ui.entry_end_time, 1)
        self.mapper.addMapping(self.ui.entry_description, 2)
        self.ui.button_save.clicked.connect(self.mapper.submit)

        # Set up default volume
        self.set_volume(self.ui.slider_volume.value())

        self.vlc_events = self.media_player.event_manager()
        self.vlc_events.event_attach(
            vlc.EventType.MediaPlayerTimeChanged, self.media_time_change_handler
        )

        # Let our application handle mouse and key input instead of VLC
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
        # When the video finishes
        self.ui.slider_progress.blockSignals(False)
        if self.media_started_playing and not self.media_player.is_playing():
            self.play_pause_model.setState(True)
            # Apparently we need to reset the media, otherwise the player
            # won't play at all
            self.media_player.set_media(self.media_player.get_media())
            self.set_volume(self.ui.slider_volume.value())
            self.media_is_playing = False
            self.media_started_playing = False

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
        if event.key() == Qt.Key_Space:
            self.play_pause()

    def wheel_handler(self, event):
        self.modify_volume(1 if event.angleDelta().y() > 0 else -1)

    def toggle_mute(self):
        self.media_player.audio_set_mute(not self.media_player.audio_get_mute())
        self.mute = not self.mute
        self.mute_model.setState(not self.mute)


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
                slider_start_pos = (self.media_start_time / duration) * \
                                   (self.ui.slider_progress.maximum() -
                                    self.ui.slider_progress.minimum())
                slider_end_pos = (self.media_end_time / duration) * \
                                 (self.ui.slider_progress.maximum() -
                                  self.ui.slider_progress.minimum())
                self.ui.slider_progress.set_highlight(
                    int(slider_start_pos), int(slider_end_pos)
                )

            else:
                self.media_start_time = 0
                self.media_end_time = -1
            self.media_player.play()
            self.media_player.set_time(self.media_start_time)
            self.media_started_playing = True
            self.media_is_playing = True
            self.play_pause_model.setState(False)
        except Exception as ex:
            self._show_error(str(ex))
            print(traceback.format_exc())

    def play_pause(self):
        """Toggle play/pause status
        """
        print(self.media_started_playing)
        print(self.media_is_playing)
        if not self.media_started_playing:
            self.run()
            return
        if self.media_is_playing:
            self.media_player.pause()
        else:
            self.media_player.play()
        self.media_is_playing = not self.media_is_playing
        self.play_pause_model.setState(not self.media_is_playing)


    def toggle_full_screen(self):
        if self.is_full_screen:
            # TODO Artifacts still happen some time when exiting full screen
            # in X11
            self.ui.frame_media.showNormal()
            self.ui.frame_media.restoreGeometry(self.original_geometry)
            self.ui.frame_media.setParent(self.ui.widget_central)
            self.ui.layout_main.addWidget(self.ui.frame_media, 2, 3, 3, 1)
            # self.ui.frame_media.ensurePolished()
        else:
            self.ui.frame_media.setParent(None)
            self.ui.frame_media.setWindowFlags(Qt.FramelessWindowHint |
                                               Qt.CustomizeWindowHint)
            self.original_geometry = self.ui.frame_media.saveGeometry()
            desktop = QApplication.desktop()
            rect = desktop.screenGeometry(desktop.screenNumber(QCursor.pos()))
            self.ui.frame_media.setGeometry(rect)
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
        self.set_timestamp_filename(QDir.toNativeSeparators(tmp_name))

    def set_timestamp_filename(self, filename):
        """
        Set the timestamp file name
        """
        if not os.path.isfile(filename):
            self._show_error("Cannot access timestamp file " + filename)
            return

        try:
            self.timestamp_model = TimestampModel(filename, self)
            self.ui.list_timestamp.setModel(self.timestamp_model)

            self.timestamp_filename = filename
            self.ui.entry_timestamp.setText(self.timestamp_filename)

            self.mapper.setModel(self.timestamp_model)
            self.mapper.addMapping(self.ui.entry_start_time, 0)
            self.mapper.addMapping(self.ui.entry_end_time, 1)
            self.mapper.addMapping(self.ui.entry_description, 2)
            self.ui.list_timestamp.selectionModel().selectionChanged.connect(
                self.timestamp_selection_changed)

            directory = os.path.dirname(self.timestamp_filename)
            basename = os.path.basename(self.timestamp_filename)
            timestamp_name_without_ext = os.path.splitext(basename)[0]
            for file_in_dir in os.listdir(directory):
                current_filename = os.path.splitext(file_in_dir)[0]
                found_video = (current_filename == timestamp_name_without_ext
                               and file_in_dir != basename)
                if found_video:
                    found_video_file = os.path.join(directory, file_in_dir)
                    self.set_video_filename(found_video_file)
                    break
        except ValueError as err:
            self._show_error("Timestamp file is invalid")

    def timestamp_selection_changed(self, selected, deselected):
        if len(selected) > 0:
            self.mapper.setCurrentModelIndex(selected.indexes()[0])
            self.ui.button_save.setEnabled(True)
            self.ui.entry_start_time.setReadOnly(False)
            self.ui.entry_end_time.setReadOnly(False)
            self.ui.entry_description.setReadOnly(False)
        else:
            self.mapper.setCurrentModelIndex(QModelIndex())
            self.ui.button_save.setEnabled(False)
            self.ui.entry_start_time.clear()
            self.ui.entry_end_time.clear()
            self.ui.entry_description.clear()
            self.ui.entry_start_time.setReadOnly(True)
            self.ui.entry_end_time.setReadOnly(True)
            self.ui.entry_description.setReadOnly(True)

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
            self.media_is_playing = False
            self.play_pause_model.setState(True)

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
        self.set_video_filename(QDir.toNativeSeparators(tmp_name))

    def _show_error(self, message, title="Error"):
        QMessageBox.warning(self, title, message)


