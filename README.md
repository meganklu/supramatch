# Supramatch

A Python program for matching host metal–organic cages to guest molecules based on packing coefficient and guest molecule price.

## Requirements

- **Python**: 3.12+
- **Operating System**: Linux, macOS, or Windows
- **Disk Space**: ~2 GB for conda environment

## Quick Start

### Installation

```bash
# 1. Clone repository
git clone https://github.com/meganklu/supramatch.git
cd supramatch

# 2. Create and activate conda environment
conda env create -f environment.yml
conda activate supramatch_env

# 3. Verify installation
python -c "
import CageCavityCalc
import rdkit
import sqlalchemy
import click
print('✓ All packages installed successfully')
"
```

### Command Line

```bash
# 1. Initialize Database
python -m supramatch.db.database init

# 2. Add Cage
python -m supramatch.modules.cage_calc data/cage.pdb --name MyCage --cas XX-XX-X

# 3. Add Guest
python -m supramatch.modules.guest_calc c1ccccc1 --name Benzene --mass 78.11 --cas 71-43-2 --supplier Sigma-Aldrich --price 66.10 --state liquid --url "https://www.sigmaaldrich.com/US/en/product/sial/401765?srsltid=AfmBOorEti16SKK4bnwJ6WVzfspI86AYKTrERWWSVn3sCkd3fbFlpADa"

# 4. Create Pairings
python -m supramatch.modules.matcher 1 create

# 5. Find Matches
python -m supramatch.modules.matcher 1 match --pc-min 0.3 --pc-max 0.7 --max-price 5.0 --min_price 1.0 --sort quality_score --limit 10
```

## References
* [RDKit Documentation](https://rdkit.org/)
* [SQLAlchemy Documentation](https://docs.sqlalchemy.org/en/20/)
* [CIRpy Documentation](https://cirpy.readthedocs.io/en/latest/#)
* [CageCavityCalc Documentation](https://github.com/VicenteMartiCentelles/CageCavityCalc)