#!/usr/bin/env python

"""
File: guest_dir.py
Author: Megan K. Lu
Date: 06/16/2026
Description: This module contains functions to read and write a directory of guest molecule files.
"""

from datetime import datetime

def init(dir):
    """
    Initialize a directory for use as a guest molecule directory.

    Args:
        dir: the name of the guest molecule directory.

    Returns:
        True if the directory was successfully marked as a scraper-created directory.
        False if the directory is NULL or the marker file could not be created.

    Note:
        The directory must already exist. The function does not create it.
    """

    scraper_file = dir + "/.scraper"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(scraper_file, "w") as file:
            file.write(f"file created at: {current_time}\n")
        return True
    except OSError:
        return False

def save(dir, guest_ID, guest_info):
    # TODO

def validate(dir):
    # TODO

def load(dir, guest_ID):
    # TODO
