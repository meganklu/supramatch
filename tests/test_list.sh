#!/bin/bash
#
# Test for monothiol cage
# Run from inside the supramatch/tests directory

export DATABASE_PATH=../data/supramatch.db

eval "$(conda shell.bash hook)"
conda activate supramatch_env

supramatch db init

supramatch cage load ./data/zd001_Picture_1.pdb
supramatch cage show 1

while IFS= read -r guest || [[ -n "$guest" ]]; do
    supramatch guest fetch "$guest"
done < ./data/guest_list.txt

supramatch match create 1
supramatch match info 1
supramatch match find 1

supramatch price lookup --cage 1
supramatch match find 1

supramatch db status
