# Supramatch

A Python program for matching host metal–organic cages to guest molecules based on packing coefficient and guest molecule price.

## Quick Start

### Installation

```bash
# 1. Clone repository
git clone https://github.com/meganklu/supramatch.git
cd supramatch

# 2. Create and activate conda environment
# (this installs Python, RDKit, OpenBabel via conda, then
# pip-installs the rest of requirements.txt into the new environment)
conda env create -f environment.yml
conda activate supramatch_env

# 3. Install the supramatch package itself
pip install -e .
```

Step 3 installs Supramatch in editable mode and registers the `supramatch`
CLI entry point defined in `pyproject.toml`. Use `pip install .` instead
of `-e .` if you don't need local edits to be picked up automatically.

#### Updating an existing environment

`pip install -r requirements.txt` (or `conda env update -f environment.yml`)
skips any package it considers already installed -- it does **not** notice
that `chemprice`'s pinned commit in `requirements.txt` changed, since the
package name is the same either way. If `requirements.txt` bumps the
`chemprice` SHA, force it explicitly before syncing the rest:

```bash
conda activate supramatch_env
pip install --force-reinstall --no-deps "chemprice @ git+https://github.com/meganklu/ChemPrice.git@<new-sha>"
pip install -r requirements.txt
```

### Configuration

Supramatch is configured via environment variables, loaded from a `.env`
file in the project root. Copy the example file and fill in what you need:

```bash
cp .env.example .env
```

Everything in `.env.example` has a working default (see
`supramatch/config.py`), so an empty `.env` is fine to start. The one
exception is vendor pricing: `supramatch price lookup` needs at least one
of `MCULE_API_KEY` / `MOLPORT_API_KEY` / `CHEMSPACE_API_KEY` set, or lookups will run but find
nothing.

### Command Line

Execute the following command to see information on command line usage:

```bash
supramatch --help
```

## References
* [RDKit Documentation](https://rdkit.org/)
* [CageCavityCalc Documentation](https://github.com/VicenteMartiCentelles/CageCavityCalc)
* [ChemPrice Documentation](https://chemprice.readthedocs.io/en/latest/) (upstream concepts; supramatch uses [our fork](https://github.com/meganklu/ChemPrice), see requirements.txt)
* [PubChem PUG REST Documentation](https://pubchemdocs.ncbi.nlm.nih.gov/pug-rest)