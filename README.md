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

# 3. Initialize database
python -m supramatch.db.database

# 4. Verify installation
python -c "
import CageCavityCalc
import rdkit
import sqlalchemy
import click
print('✓ All packages installed successfully')
"
```