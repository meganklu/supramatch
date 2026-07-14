#!/bin/bash
#
# Test basic CLI usage
# Run from inside the supramatch/tests directory

export DATABASE_PATH=./data/supramatch.db

eval "$(conda shell.bash hook)"
conda activate supramatch_env

supramatch --help
supramatch --version
supramatch cage --help
supramatch guest --help
supramatch match --help
supramatch price --help
supramatch pipeline --help
supramatch db --help

supramatch db init
echo "y" | supramatch db reset
supramatch db init
supramatch db init  # safe to run twice

supramatch guest load c1ccccc1 --name Benzene \
  --cas 71-43-2 \
  --state liquid

echo "y" | supramatch db reset

supramatch cage load ./data/zd001_Picture_1.pdb
supramatch cage load ./data/zd001_Picture_1.pdb --name copy

supramatch cage list
supramatch cage list --limit 1

supramatch cage show 1
supramatch cage show 2 --recalculate

supramatch guest calculate c1ccccc1

supramatch guest import ./data/guests.json
supramatch guest import ./data/guests.csv
supramatch guest import ./data/guests.xml

supramatch guest load c1ccccc1 --name Benzene --cas 71-43-2
supramatch guest load "Br[C@]12C[C@@H]3C[C@H](C1)C[C@@](Br)(C3)C2"
supramatch guest load "Br[C@]12C[C@@H]3C[C@H](C1)C[C@@](Br)(C3)C2" -n 1,3-Dibromoadamantane
supramatch guest load Cc1ccccc1 --name Toluene \
  --cas 108-88-3 \
  --state liquid
supramatch guest load c1cc2ccccc2cc1 --name Naphthalene \
  --cas 91-20-3 \
  --state solid

# Fetches from PubChem live -- requires network access
supramatch guest fetch aspirin
supramatch guest fetch 50-78-2 --name "Aspirin (duplicate CAS test)"

supramatch guest list
supramatch guest list --limit 2

echo "y" | supramatch guest delete 1
supramatch guest list

supramatch guest fetch benzene

supramatch guest search toluene
supramatch guest search adamantane
supramatch guest search aspirin
supramatch guest search nonexistent-guest-xyz

supramatch match create 1
supramatch match create 2 -g 1,3,4,5

supramatch match info 1
supramatch match info 2

supramatch match find 1 --pc-ideal 0.5 --pc-tolerance 0.5
supramatch match find 1 -s packing_coefficient -i 0.55 -t 1
supramatch match find 2 -s price -i 0.5 -t 0.5

# Requires MCULE_API_KEY/MOLPORT_API_KEY/CHEMSPACE_API_KEY to actually find prices; safe to
# run without them (just prices nothing and reports 0 priced).
supramatch price lookup --cage 1
supramatch price lookup --cage 1 --all-matches --refresh
supramatch price lookup --guest 11
supramatch price lookup --guest 11 --refresh
supramatch price list 11

supramatch match find 1

# Full pipeline in one command, reusing the cage/guests already loaded above
supramatch pipeline run --cage-id 1 --guest-id 11 --guest-id 2 --all-matches --limit 5
supramatch pipeline run --cage-id 1 --guest-id 11 --guest-id 3 --refresh-prices --sort price --pc-ideal 0.5 --pc-tolerance 0.5
supramatch pipeline run --cage-pdb ./data/zd001_Picture_1.pdb --cage-name "Pipeline Cage" --guest caffeine --guest ibuprofen

supramatch db status

# Error / edge cases -- these are expected to fail and print a red error message
supramatch cage show 999
supramatch cage load ./data/does_not_exist.pdb
supramatch guest load not-a-valid-smiles --name fake
supramatch match find 999
supramatch match create 999
supramatch price lookup
supramatch price lookup --cage 1 --guest 1
supramatch pipeline run --guest caffeine
supramatch pipeline run --cage-id 1 --cage-pdb ./data/zd001_Picture_1.pdb --guest caffeine
supramatch pipeline run --cage-id 1

echo "y" | supramatch cage delete 2
supramatch cage list
