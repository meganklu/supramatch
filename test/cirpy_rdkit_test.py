import cirpy
from rdkit import Chem
from rdkit.Chem import AllChem

cas = '876-53-9'
smiles = cirpy.resolve(cas, 'smiles')
mol = Chem.MolFromSmiles(smiles) # load molecule from smiles
mol = Chem.AddHs(mol) # add hydrogens
AllChem.EmbedMolecule(mol, randomSeed=0xf00d) # embed to add 3D coordinates with optional random seed for reproducibility
AllChem.MMFFOptimizeMolecule(mol) # optimize conformer with a force field
volume = AllChem.ComputeMolVolume(mol) # calculate volume
print("Molecular_volume= ", volume, " A3")
