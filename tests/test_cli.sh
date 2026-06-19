#!/bin/bash
#
# Test basic CLI usage

conda init
conda activate supramatch_env

supramatch --help
supramatch --version
supramatch cage --help
supramatch guest --help
supramatch match --help
supramatch db --help

supramatch db init

supramatch guest load c1ccccc1 --name Benzene \
  --cas 71-43-2 \
  --supplier "Sigma-Aldrich" \
  --price 0.59 \
  --state liquid \
  --url "https://www.sigmaaldrich.com/..."

echo "y" | supramatch db reset

supramatch cage load ../data/tests/zd001_Picture_1.pdb
supramatch cage load ../data/tests/zd001_Picture_1.pdb --name copy

supramatch cage list

supramatch cage show 1
supramatch cage show 2 --recalculate

supramatch guest calculate c1ccccc1

supramatch guest import ../data/tests/guests.json

supramatch guest load c1ccccc1 --name Benzene --cas 71-43-2 --price 0.59 -s "Sigma-Aldrich"
supramatch guest load "Br[C@]12C[C@@H]3C[C@H](C1)C[C@@](Br)(C3)C2"
supramatch guest load "Br[C@]12C[C@@H]3C[C@H](C1)C[C@@](Br)(C3)C2" -n 1,3-Dibromoadamantane
supramatch guest load Cc1ccccc1 --name Toluene \
  --cas 108-88-3 \
  --supplier "Sigma-Aldrich" \
  --price 0.45 \
  --state liquid
supramatch guest load c1cc2ccccc2cc1 --name Naphthalene \
  --cas 91-20-3 \
  --supplier "Sigma-Aldrich" \
  --price 1.85 \
  --state solid

supramatch guest list
supramatch guest list -s "Sigma-Aldrich"
supramatch guest list --limit 2

supramatch guest search toluene
supramatch guest search adamantane

supramatch match create 1
supramatch match create 2 -g 1,3,4,5

supramatch match info 1
supramatch match info 2

supramatch match find 1 --pc-ideal 0.5 --pc-tolerance 0.5
supramatch match find 1 -s packing_coefficient -i 0.55 -t 1
supramatch match find 2 -s price -i 0.5 -t 0.5

supramatch db status

echo "y" | supramatch guest delete 1
supramatch guest list

echo "y" | supramatch cage delete 2
supramatch cage list

echo "y" | supramatch db drop