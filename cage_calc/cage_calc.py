#!/usr/bin/env python

"""
File: cage_calc.py
Author: Megan K. Lu
Date: 06/16/2026
Description: This module calculates the volume of the cage cavity and saves the cage information to a file.
"""

import sys
from CageCavityCalc.CageCavityCalc import cavity

def calculate_volume(cage_pdb_file):
    """
    Calculates the volume of the cage cavity.

    Args:
        cage_pdb_file: the name of cage.pdb file.

    Returns:
        The volume of the cage cavity.
    """

    grid_spacing = 0.5
    distance_threshold_for_90_deg_angle = 2.0
    cav = cavity()
    cav.read_file(cage_pdb_file)
    window_radius = cav.calculate_window()
    cav.distance_threshold_for_90_deg_angle = window_radius * distance_threshold_for_90_deg_angle
    if cav.distance_threshold_for_90_deg_angle < 5:
        cav.distance_threshold_for_90_deg_angle = 5
    cav.grid_spacing = float(grid_spacing)
    cav.dummy_atom_radii = float(grid_spacing)
    volume = cav.calculate_volume()
    return volume

def save(cage_pdb_file, volume, cage_info_file):
    """
    Saves the cage information to a file.

    Args:
        cage_pdb_file: the name of cage.pdb file.
        volume: the calculated volume of the cage cavity.
        cage_info_file: the name of the cage info file.

    Returns:
        True if the cage info file was successfully created.
        False if error encountered.
    """

    # Read first line of pdb file for cage name
    cage_name = "N/A"
    with open(cage_pdb_file, "r") as file:
        for line in file:
            if line.startswith("COMPND"):
                cage_name = line[6:].strip()
                break

    try:
        with open(cage_info_file, "w") as file:
            file.write(f"name: {cage_name}\n")
            file.write(f"cavity volume (A3): {volume}\n")
        return True
    except OSError:
        return False
    
def main(args):
    if len(args) < 3:
        print("Error: Missing required argument(s).", file=sys.stderr)
        return 1

    cage_pdb_file = args[1]
    cage_info_file = args[2]
    volume = calculate_volume(cage_pdb_file)
    if save(cage_pdb_file, volume, cage_info_file):
        return 0
    else:
        print("Error: Unable to create cage info file.", file=sys.stderr)
        return 2

if __name__ == "__main__":
    # sys.exit catches the returned integer from main() and terminates the process
    sys.exit(main(sys.argv))
