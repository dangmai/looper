#!/usr/bin/env python

"""
Program to loop videos based on timestamps in a text file
"""

import argparse
import loop
import os
import sys

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, \
    QMessageBox, QTreeWidget, QTreeWidgetItem


class MainWindow(QMainWindow):
    """
    The main window class
    """
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.ui = uic.loadUi("main_window.ui")

        self.timestamp_filename = None
        self.video_filename = None

        self.ui.button_run.clicked.connect(self.run)
        self.ui.button_timestamp_browse.clicked.connect(
            self.browse_timestamp_handler
        )
        self.ui.button_video_browse.clicked.connect(
            self.browse_video_handler
        )
        self.ui.show()

    def run(self):
        """
        Execute the loop
        """
        if self.timestamp_filename is None:
            QMessageBox.warning(self, "Error", "No timestamp file chosen")
            return
        if self.video_filename is None:
            QMessageBox.warning(self, "Error", "No video file chosen")
            return
        selected_timestamps = self.ui.list_timestamp.selectedItems()
        if not selected_timestamps:
            QMessageBox.warning(self, "Error", "No timestamp chosen")
            return

        try:
            loop.play_video(
                self.video_filename,
                self.timestamp_filename,
                int(selected_timestamps[0].text(0))
            )
        except Exception as ex:
            QMessageBox.warning(self, "Error", str(ex))

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
            QMessageBox.warning(
                self, "Error", "Cannot access timestamp file " + filename)
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
            QMessageBox.warning(
                self, "Error", "Cannot select timestamp #" + str(num))
            return
        self.ui.list_timestamp.setCurrentItem(
            self.ui.list_timestamp.topLevelItem(num - 1)
        )

    def set_video_filename(self, filename):
        """
        Set the video filename
        """
        if not os.path.isfile(filename):
            QMessageBox.warning(
                self, "Error", "Cannot access video file " + filename)
            return
        self.video_filename = filename
        self.ui.entry_video.setText(self.video_filename)

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
