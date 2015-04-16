#!/usr/bin/env python

"""
Program to loop videos based on timestamps in a text file
"""

import argparse
import datetime
import logging
import os
import subprocess


def main():
    """
    Main function for the program
    """
    parser = argparse.ArgumentParser(
        description="Loop a video between 2 points in time based on rules in "
                    "a text file."
    )
    parser.add_argument('video_file', metavar='V',
                        help='the location of the video file')
    parser.add_argument('timestamp_file', metavar='F',
                        help='the location of the timestamp file')
    parser.add_argument('timestamp_num', metavar='N', type=int,
                        help='which timestamp to use')
    parser.add_argument('--debug', action='store_true', default=False,
                        help='print the debug information to the screen')
    args = parser.parse_args()
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if args.debug:
        log_formatter = logging.Formatter(
            "%(asctime)s [%(threadName)-12.12s] "
            "[%(levelname)-5.5s]  %(message)s"
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)

    logger.info('Started')
    play_video(args.video_file, args.timestamp_file, args.timestamp_num)

def play_video(video_file, timestamp_file, timestamp_num):
    """
    Loop the video using VLC
    """
    if not os.path.isfile(video_file):
        raise FileNotFoundError('Cannot access file: ' + video_file)
    start_delta, end_delta = parse_line_in_timestamp_file(timestamp_file, timestamp_num)
    process = subprocess.Popen([
        'vlc', video_file, '--start-time', str(start_delta.seconds),
        '--stop-time', str(end_delta.seconds), '--repeat'
    ])
    process.communicate()


def parse_line_in_timestamp_file(timestamp_file, timestamp_num):
    if not os.path.isfile(timestamp_file):
        raise FileNotFoundError('Cannot access file: ' + timestamp_file)
    timestamp_file = open(timestamp_file, 'r')
    lines = timestamp_file.readlines()
    timestamp_file.close()
    if len(lines) < timestamp_num or timestamp_num < 1:
        raise ValueError("Timestamp num is not valid")
    line = lines[timestamp_num - 1]  # We use human-friendly index here
    start_delta, end_delta, _ = parse_line(line)
    return start_delta, end_delta


def parse_line(line):
    """
    Given a line of the timestamp file, return the start delta, end delta and
    description
    """
    start_time = line.split('-')[0]
    end_time = line.split('-')[1]
    start_min, start_sec = [int(a) for a in start_time.split(':')]
    end_min, end_sec = [int(a) for a in end_time.split(':')]
    start_delta = datetime.timedelta(minutes=start_min, seconds=start_sec)
    end_delta = datetime.timedelta(minutes=end_min, seconds=end_sec)
    return start_delta, end_delta, line.split('-', maxsplit=2)[2].strip()

if __name__ == '__main__':
    main()
