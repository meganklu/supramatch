# Guest Directory

`guest_dir.py` contains functions to read and write a directory of guest molecule files. Each guest molecule has a file whose name is an integer (`1`, `2`, etc.). 

## Functions

* `init`: initialize a directory for use as a guest molecule directory
* `save`: save a guest molecule to a file in the guest molecule directory
* `validate`: verify that a directory is a valid scraper-produced guest molecule directory
* `load`: load a guest molecule from a file in the guest molecule directory

## Guest Molecule Directory Structure

A valid guest molecule directory will contain:

* A readable `.scraper` marker file with the date the file was created
* A readable guest molecule file named `1`

## Guest Molecule File Structure

A guest molecule file will follow the format shown in this example:

```
name: 1,3-Dibromoadamantane
product number: 403083
price ($/g): 75.75
empirical formula: C10H14Br2
CAS number: 876-53-9
molecular weight: 294.03
form: powder
mp: 108-110 °C (lit.)
bp: N/A
functional group: bromo
SMILES string: Br[C@]12C[C@@H]3C[C@H](C1)C[C@@](Br)(C3)C2
```
