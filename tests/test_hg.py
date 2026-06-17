from CageCavityCalc.CageCavityCalc import cavity

import cirpy
from rdkit import Chem
from rdkit.Chem import AllChem

cage_name = "../data/zd001_Picture_1"
grid_spacing = 0.5
distance_threshold_for_90_deg_angle = 2.0
cav = cavity()
cav.read_file(cage_name+".pdb")
window_radius = cav.calculate_window()
cav.distance_threshold_for_90_deg_angle = window_radius * distance_threshold_for_90_deg_angle
if cav.distance_threshold_for_90_deg_angle < 5:
    cav.distance_threshold_for_90_deg_angle = 5
cav.grid_spacing = float(grid_spacing)
cav.dummy_atom_radii = float(grid_spacing)
cavity_volume = cav.calculate_volume()
print("Cavity_volume= ", cavity_volume, " A3")

cas = '876-53-9'
smiles = cirpy.resolve(cas, 'smiles')
mol = Chem.MolFromSmiles(smiles) # load molecule from smiles
mol = Chem.AddHs(mol) # add hydrogens
AllChem.EmbedMolecule(mol, randomSeed=0xf00d) # embed to add 3D coordinates with optional random seed for reproducibility
AllChem.MMFFOptimizeMolecule(mol) # optimize conformer with a force field
molecular_volume = AllChem.ComputeMolVolume(mol) # calculate volume
print("Molecular_volume= ", molecular_volume, " A3")

packing_coefficient = molecular_volume / cavity_volume
print("Packing_coefficient= ", packing_coefficient)
