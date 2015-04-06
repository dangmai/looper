#!/usr/bin/env python

"""
The GUI to the program
"""

import argparse
import loop
import os
import tkinter as tk

from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk


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
    app = Application()
    app.master.title('Video Loop')

    if args.timestamp_filename:
        timestamp_filename = os.path.abspath(args.timestamp_filename)
        if os.path.isfile(timestamp_filename):
            app.set_timestamp_filename(timestamp_filename)
            if args.timestamp_num:
                app.set_timestamp_num(args.timestamp_num)
    if args.video_filename:
        video_filename = os.path.abspath(args.video_filename)
        if os.path.isfile(video_filename):
            app.set_video_filename(video_filename)

    app.mainloop()

class Application(tk.Frame):
    def __init__(self, master=None):
        self.timestamp_filename = None
        self.video_filename = None

        tk.Frame.__init__(self, master)
        self.grid()

        self.timestamp_label = tk.Label(self, text='Timestamp File')
        self.timestamp_label.grid(row=0, column=0)

        self.timestamp_entry = tk.Text(
            self, state='disabled', width=60, height=1
        )
        self.timestamp_entry.grid(row=0, column=1)

        self.timestamp_button = tk.Button(
            self, text='Browse', command=self.get_timestamp_filename
        )
        self.timestamp_button.grid(row=0, column=2)

        self.video_label = tk.Label(self, text='Video File')
        self.video_label.grid(row=1, column=0)

        self.video_entry = tk.Text(
            self, state='disabled', width=60, height=1
        )
        self.video_entry.grid(row=1, column=1)

        self.video_button = tk.Button(
            self, text='Browse', command=self.get_video_filename
        )
        self.video_button.grid(row=1, column=2)

        self.tree_view = ttk.Treeview(
            self, show='headings', selectmode='browse'
        )
        self.tree_view["columns"] = (
            "num", "start_time", "end_time", "description"
        )
        self.tree_view.column("num", width=20)
        self.tree_view.column("start_time", minwidth=50, width=100)
        self.tree_view.column("end_time", minwidth=50, width=100)
        self.tree_view.column("description", minwidth=100, width=400)
        self.tree_view.heading("num", text="#")
        self.tree_view.heading("start_time", text="Start Time")
        self.tree_view.heading("end_time", text="End Time")
        self.tree_view.heading("description", text="Description")
        self.tree_view.grid(row=2, columnspan=3)

        self.loop_button = tk.Button(
            self, text='Run', command=self.execute
        )
        self.loop_button.grid(row=3, column=2)

    def execute(self):
        """
        Execute the loop
        """
        if self.timestamp_filename is None:
            messagebox.showwarning(
                "Error", "No timestamp file chosen", parent=self
            )
            return
        if self.video_filename is None:
            messagebox.showwarning(
                "Error", "No video file chosen", parent=self
            )
            return
        selection = self.tree_view.selection()
        if selection is not None and len(selection) > 0:
            try:
                loop.play_video(
                    self.video_filename,
                    self.timestamp_filename,
                    self.tree_view.item(self.tree_view.selection()[0])['values'][0]
                )
            except Exception as ex:
                messagebox.showwarning(
                    "Error", str(ex), parent=self
                )
        else:
            messagebox.showwarning("Error", "No timestamp chosen", parent=self)

    def get_timestamp_filename(self):
        """
        Get the timestamp file from the file dialog
        """
        tmp_file_name = filedialog.askopenfilename(
            filetypes=[('Timestamp files', '.tmsp')]
        )
        if not tmp_file_name:
            return
        self.set_timestamp_filename(tmp_file_name)

    def set_timestamp_filename(self, filename):
        self.timestamp_filename = filename
        self.timestamp_entry.config(state='normal')
        self.timestamp_entry.delete(1.0, tk.END)
        self.timestamp_entry.insert(1.0, self.timestamp_filename)
        self.timestamp_entry.config(state='disabled')
        for item in self.tree_view.get_children():
            self.tree_view.delete(item)
        with open(self.timestamp_filename, 'r') as timestamp_file:
            for index, line in enumerate(timestamp_file):
                start_delta, end_delta, description = loop.parse_line(line)
                self.tree_view.insert(
                    "", "end", values=(
                        index + 1, str(start_delta), str(end_delta), description
                    )
                )
        directory = os.path.dirname(self.timestamp_filename)
        basename = os.path.basename(self.timestamp_filename)
        name_without_ext = os.path.splitext(basename)[0]
        for file_in_dir in os.listdir(directory):
            if os.path.splitext(file_in_dir)[0] == name_without_ext and file_in_dir != basename:
                found_video_file = os.path.join(directory, file_in_dir)
                self.video_filename = found_video_file
                self.video_entry.config(state='normal')
                self.video_entry.delete(1.0, tk.END)
                self.video_entry.insert(1.0, self.video_filename)
                self.video_entry.config(state='disabled')
                break

    def get_video_filename(self):
        """
        Get the video file from the file dialog
        """
        tmp_file_name = filedialog.askopenfilename()
        if not tmp_file_name:
            return
        self.set_video_filename(tmp_file_name)

    def set_video_filename(self, filename):
        self.video_filename = filename
        self.video_entry.config(state='normal')
        self.video_entry.delete(1.0, tk.END)
        self.video_entry.insert(1.0, self.video_filename)
        self.video_entry.config(state='disabled')

    def set_timestamp_num(self, num):
        all_children = self.tree_view.get_children()
        print(all_children)
        if num > len(all_children) and num > 0:
            return
        timestamp_id = self.tree_view.get_children()[num-1]
        print(timestamp_id)
        self.tree_view.selection_set(timestamp_id)


if __name__ == '__main__':
    main()
