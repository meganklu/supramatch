"""
Calculate guest properties, import from files, and manage database operations.

Volumes calculated from SMILES using RDKit's ComputeMolVolume()

Supported Import Formats:
    - XML
    - CSV
    - JSON

Note:
    Pricing is not part of guest creation -- it's looked up separately via
    ChemPrice (see supramatch.discovery.price_lookup) and stored in the
    `prices` table, since a guest can have quotes from multiple vendors.
"""

import logging
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from supramatch.db import queries
from supramatch.db.database import get_connection, close_connection
from supramatch.models.guest import Guest
from supramatch.discovery import pubchem_client
from supramatch.config import GUEST_CALC_CONFIG
from supramatch.utils.helpers import format_volume

logger = logging.getLogger(__name__)

class GuestCalculator:
    """
    Handles guest molecule calculations and database operations.

    Volumes:
        All calculations are in Å³
        Volume calculated via RDKit using the rdkit.Chem.AllChem module
    """

    def __init__(self):
        self.conn = get_connection()

        # Load config parameters
        self.random_seed = GUEST_CALC_CONFIG["random_seed"]
        self.optimize_geometry = GUEST_CALC_CONFIG["optimize_geometry"]

        logger.debug(
            f"GuestCalculator initialized with config: "
            f"random_seed={self.random_seed}, "
            f"optimize_geometry={self.optimize_geometry}"
        )

    # ==================== CALCULATIONS ====================

    def calculate_volume(self, smiles: str) -> float:
        """
        Calculates the volume of a guest molecule from SMILES.

        Args:
            smiles: SMILES string for the guest molecule.

        Returns:
            float: The volume of the guest molecule in Å³.

        Raises:
            ValueError: If SMILES is invalid or calculation fails.

        Example:
            >>> calc = GuestCalculator()
            >>> volume = calc.calculate_volume('c1ccccc1')  # Benzene
            >>> print(f"Volume: {volume:.2f} Å³")
            Volume: 89.20 Å³
        """
        logger.debug(f"Calculating volume for SMILES: {smiles}")

        if not smiles or not isinstance(smiles, str):
            logger.error("Invalid SMILES: must be non-empty string")
            raise ValueError("SMILES must be a non-empty string")

        try:
            mol = Chem.MolFromSmiles(smiles)

            if mol is None:
                logger.error(f"Invalid SMILES string: {smiles}")
                raise ValueError(f"Invalid SMILES string: {smiles}")

            logger.debug(f"SMILES parsed successfully")

            # Add hydrogens
            mol = Chem.AddHs(mol)

            # Embed molecule with 3D coordinates
            conf_id = AllChem.EmbedMolecule(mol, randomSeed=self.random_seed)

            if conf_id == -1:
                # Fallback for difficult molecules
                logger.debug(f"Failed to embed with seed, using ETKDG")
                AllChem.EmbedMolecule(mol, AllChem.ETKDG())

            # Optimize geometry
            if self.optimize_geometry:
                logger.debug(f"Optimizing molecular geometry")
                AllChem.MMFFOptimizeMolecule(mol)

            # Calculate volume (in cubic angstroms)
            volume = AllChem.ComputeMolVolume(mol)
            volume_str = format_volume(volume)
            logger.debug(f"Volume calculated: {volume_str}")

            if volume is None or volume <= 0:
                logger.error(f"Invalid volume: {volume}")
                raise ValueError("Invalid volume calculation result")

            logger.info(f"Successfully calculated volume for SMILES: {volume_str}")
            return volume

        except Exception as e:
            logger.error(f"Failed to calculate volume: {e}", exc_info=True)
            raise ValueError(f"Failed to calculate volume for SMILES '{smiles}': {e}")

    def calculate_rotatable_bonds(self, smiles: str) -> int:
        """
        Calculates the number of rotatable bonds in a guest molecule from SMILES.

        Used as a proxy for conformational flexibility -- see
        Guest.rotatable_bonds and Match.quality_score for how it factors
        into match scoring. Unlike calculate_volume, this only needs the 2D
        graph (no 3D embedding), so it's cheap and can't fail the way
        embedding sometimes does for strained/unusual structures.

        Args:
            smiles: SMILES string for the guest molecule.

        Returns:
            int: Number of rotatable bonds.

        Raises:
            ValueError: If SMILES is invalid.

        Example:
            >>> calc = GuestCalculator()
            >>> calc.calculate_rotatable_bonds('c1ccccc1')  # Benzene
            0
        """
        logger.debug(f"Calculating rotatable bonds for SMILES: {smiles}")

        if not smiles or not isinstance(smiles, str):
            logger.error("Invalid SMILES: must be non-empty string")
            raise ValueError("SMILES must be a non-empty string")

        mol = Chem.MolFromSmiles(smiles)

        if mol is None:
            logger.error(f"Invalid SMILES string: {smiles}")
            raise ValueError(f"Invalid SMILES string: {smiles}")

        rotatable_bonds = Descriptors.NumRotatableBonds(mol)
        logger.info(f"Successfully calculated rotatable bonds for SMILES: {rotatable_bonds}")
        return rotatable_bonds

    # ==================== DATABASE OPERATIONS ====================

    def create_guest(
        self,
        name: str,
        smiles: str,
        molecular_weight: float = None,
        iupac_name: str = None,
        molecular_formula: str = None,
        pubchem_cid: int = None,
        cas_number: str = None,
        physical_state: str = None,
    ) -> Guest:
        """
        Create a new guest molecule in the database with calculated properties.

        Args:
            name: Common name of the molecule.
            smiles: SMILES string.
            molecular_weight: Molecular weight in g/mol.
            iupac_name: Formal IUPAC name (optional; e.g. from PubChem).
            molecular_formula: Molecular formula, e.g. "C9H8O4" (optional).
            pubchem_cid: PubChem CID this guest was fetched from, for
                provenance (optional; set automatically by create_guest_from_pubchem).
            cas_number: CAS registry number.
            physical_state: 'solid', 'liquid', or 'gas'. Always manually supplied
                (e.g. via `guest load`/`guest import`) -- PubChem's physical-state
                data (`guest fetch`) is curated free text with thin coverage and,
                confirmed by testing, can be actively misleading (e.g. methane's
                data includes a "Liquid" entry referring to its cryogenic storage
                form, not its state at room temperature), so it's not auto-derived.

        Returns:
            Guest: The created guest object.

        Raises:
            ValueError: If guest already exists, SMILES invalid, or calculation fails.

        Example:
            >>> calc = GuestCalculator()
            >>> guest = calc.create_guest(name='Benzene', smiles='c1ccccc1')
            >>> print(f"Created: {guest.name}")
            >>> print(f"Volume: {guest.molecular_volume:.2f} Å³")
        """
        logger.info(f"Creating guest: {name}")
        logger.debug(f"SMILES: {smiles}, CAS: {cas_number}")

        if not name or not isinstance(name, str):
            logger.error("Name must be a non-empty string")
            raise ValueError("Name must be a non-empty string")

        if not smiles or not isinstance(smiles, str):
            logger.error("SMILES must be a non-empty string")
            raise ValueError("SMILES must be a non-empty string")

        # Check if an identical guest already exists, by CAS number, SMILES, or name
        if cas_number:
            existing = queries.get_guest_by_cas(self.conn, cas_number)
            if existing:
                logger.warning(f"Guest with CAS number '{cas_number}' already exists in database")
                raise ValueError(f"Guest with CAS number '{cas_number}' already exists in database")

        existing = queries.get_guest_by_smiles(self.conn, smiles)
        if existing:
            logger.warning(f"Guest with SMILES '{smiles}' already exists in database (as '{existing.name}')")
            raise ValueError(f"Guest with SMILES '{smiles}' already exists in database (as '{existing.name}')")

        existing = queries.get_guest_by_name(self.conn, name)
        if existing:
            logger.warning(f"Guest with name '{name}' already exists in database")
            raise ValueError(f"Guest with name '{name}' already exists in database")

        # Validate molecular weight
        if molecular_weight is not None and molecular_weight < 0:
            logger.error("Molecular weight cannot be negative")
            raise ValueError("Molecular weight cannot be negative")

        # Validate physical state
        valid_states = {'solid', 'liquid', 'gas'}
        if physical_state and physical_state.lower() not in valid_states:
            logger.error(f"Physical state must be one of {valid_states}")
            raise ValueError(f"Physical state must be one of {valid_states}")

        try:
            # Calculate properties
            logger.debug(f"Calculating properties for {name}")
            molecular_volume = self.calculate_volume(smiles)
            volume_str = format_volume(molecular_volume)
            rotatable_bonds = self.calculate_rotatable_bonds(smiles)

            # Create guest record
            guest = queries.create_guest(
                self.conn,
                name=name,
                smiles=smiles,
                molecular_volume=molecular_volume,
                molecular_weight=molecular_weight,
                iupac_name=iupac_name,
                molecular_formula=molecular_formula,
                rotatable_bonds=rotatable_bonds,
                pubchem_cid=pubchem_cid,
                cas_number=cas_number,
                physical_state=physical_state.lower() if physical_state else None,
            )

            logger.info(f"Created guest '{name}': Volume={volume_str}, RotatableBonds={rotatable_bonds}")
            return guest

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to create guest {name}: {e}", exc_info=True)
            raise

    def create_guest_from_pubchem(
        self,
        query: str,
        name: str = None,
        physical_state: str = None,
    ) -> Guest:
        """
        Resolve a compound on PubChem by name/CAS number and create a guest from it.

        This is the one place PubChem data and guest creation meet -- both
        the `guest fetch` CLI command and any library/script usage should
        call this rather than combining pubchem_client and create_guest
        themselves, so there's a single source of truth for how a fetched
        compound becomes a guest.

        Args:
            query: Compound name or CAS registry number to look up.
            name: Override the guest name (defaults to PubChem's Title,
                falling back to IUPAC name, falling back to the query itself).
            physical_state: 'solid', 'liquid', or 'gas'. Not available from
                PubChem (see create_guest's docstring for why) -- supply it
                manually if wanted.

        Returns:
            Guest: The created guest object, including PubChem's CID,
                IUPAC name, and molecular formula. CAS number is only set
                if `query` was itself a CAS number (see pubchem_client's
                module docstring for why a name-based lookup can't reliably
                produce one).

        Raises:
            ValueError: If the compound can't be resolved on PubChem, or if
                guest creation fails (already exists, calculation fails, etc).

        Example:
            >>> calc = GuestCalculator()
            >>> guest = calc.create_guest_from_pubchem('aspirin')
            >>> guest = calc.create_guest_from_pubchem('50-78-2')
        """
        logger.info(f"Fetching guest from PubChem: {query}")

        compound = pubchem_client.fetch_compound(query)
        if compound is None:
            logger.warning(f"Could not resolve '{query}' on PubChem")
            raise ValueError(f"Could not find '{query}' on PubChem")

        return self.create_guest(
            name=name or compound["name"],
            smiles=compound["smiles"],
            molecular_weight=compound["molecular_weight"],
            iupac_name=compound["iupac_name"],
            molecular_formula=compound["formula"],
            pubchem_cid=compound["cid"],
            cas_number=compound["cas_number"],
            physical_state=physical_state,
        )

    def get_guest(self, guest_id: int = None, cas_number: str = None, name: str = None) -> Optional[Guest]:
        """Retrieve a guest from the database."""
        if guest_id:
            logger.debug(f"Retrieving guest with ID: {guest_id}")
            return queries.get_guest_by_id(self.conn, guest_id)
        elif cas_number:
            logger.debug(f"Retrieving guest with CAS number: {cas_number}")
            return queries.get_guest_by_cas(self.conn, cas_number)
        elif name:
            logger.debug(f"Retrieving guest with name: {name}")
            return queries.get_guest_by_name(self.conn, name)
        return None

    def search_guests(self, name_pattern: str = None) -> List[Guest]:
        """Search for guests by name."""
        logger.debug(f"Searching for guests: name_pattern={name_pattern}")
        return queries.search_guests(self.conn, name_pattern=name_pattern)

    def list_guests(self, limit: int = None, offset: int = 0) -> List[Guest]:
        """Get all guests from the database with optional pagination."""
        logger.debug("Retrieving all guests from database")
        guests = queries.list_guests(self.conn, limit=limit, offset=offset)
        logger.info(f"Found {len(guests)} guest(s) in database")
        return guests

    def recalculate_volume(self, guest_id: int) -> Optional[float]:
        """Recalculate volume for a guest from stored SMILES."""
        logger.debug(f"Recalculating volume for guest ID: {guest_id}")
        guest = queries.get_guest_by_id(self.conn, guest_id)

        if not guest:
            logger.warning(f"Guest with ID {guest_id} not found")
            return None

        if not guest.smiles:
            logger.warning(f"Guest with ID {guest_id} does not have SMILES stored")
            return None

        try:
            logger.info(f"Recalculating volume for {guest.name}")
            old_volume_str = format_volume(guest.molecular_volume)
            new_volume = self.calculate_volume(guest.smiles)
            new_volume_str = format_volume(new_volume)
            queries.update_guest_volume(self.conn, guest_id, new_volume)
            logger.info(f"Updated {guest.name} volume from {old_volume_str} to {new_volume_str}")
            return new_volume

        except Exception as e:
            logger.error(f"Failed to recalculate volume for {guest.name}: {e}")
            raise ValueError(f"Failed to recalculate volume: {e}")

    def recalculate_rotatable_bonds(self, guest_id: int) -> Optional[int]:
        """
        Recalculate rotatable bond count for a guest from stored SMILES.

        Mainly useful for backfilling guests created before this field
        existed (their rotatable_bonds is NULL, so they get no flexibility
        penalty in Match.quality_score until this is run).
        """
        logger.debug(f"Recalculating rotatable bonds for guest ID: {guest_id}")
        guest = queries.get_guest_by_id(self.conn, guest_id)

        if not guest:
            logger.warning(f"Guest with ID {guest_id} not found")
            return None

        if not guest.smiles:
            logger.warning(f"Guest with ID {guest_id} does not have SMILES stored")
            return None

        try:
            logger.info(f"Recalculating rotatable bonds for {guest.name}")
            new_rotatable_bonds = self.calculate_rotatable_bonds(guest.smiles)
            queries.update_guest_rotatable_bonds(self.conn, guest_id, new_rotatable_bonds)
            logger.info(f"Updated {guest.name} rotatable bonds from {guest.rotatable_bonds} to {new_rotatable_bonds}")
            return new_rotatable_bonds

        except Exception as e:
            logger.error(f"Failed to recalculate rotatable bonds for {guest.name}: {e}")
            raise ValueError(f"Failed to recalculate rotatable bonds: {e}")

    def batch_create_from_identifiers(
        self,
        identifiers: List[str],
        mark_in_inventory: bool = False,
    ) -> dict:
        """
        Resolve a list of compound names/CAS numbers via PubChem, creating
        guests for any not already in the database.

        Each identifier gets its own PubChem lookup (see pubchem_client's
        module docstring on why name/CAS resolution can't be batched), so
        this is network-bound and paced accordingly -- expect it to take a
        while for large lists. An identifier already present in the
        database (matched by CAS number or SMILES, whichever the resolved
        compound has) is reused rather than duplicated. A created guest's
        `cas_number` is only set when the identifier itself was a CAS
        number -- a name identifier (e.g. "aspirin") creates a guest with
        no CAS number, since PubChem can't reliably supply one for a
        name-based lookup (see pubchem_client's module docstring). If a
        matched (pre-existing) guest doesn't have a `cas_number` on file yet
        and the identifier that matched it was itself a CAS number, that CAS
        number is backfilled onto the existing guest -- this is how a guest
        originally added by name (or by an older, since-removed CAS-guessing
        heuristic) picks up a real CAS number once it's re-encountered via a
        genuine CAS-based lookup. A matched guest that already has a
        *different* CAS number on file is left untouched (matched by SMILES
        despite conflicting CAS registrations is unusual enough to need a
        person to look at it, not a silent overwrite).

        Args:
            identifiers: Compound names or CAS registry numbers.
            mark_in_inventory: If True, mark every guest this call touches --
                both newly created ones and pre-existing ones matched from
                the list -- as in inventory. Guests that fail to resolve are
                obviously not marked.

        Returns:
            dict: {
                "created": List[Guest] newly created,
                "matched": List[Guest] already existed, reused,
                "cas_filled": List[Guest] pre-existing guests whose missing
                    CAS number was backfilled from this run's identifier,
                "failed": List[dict] {"identifier": str, "error": str},
            }

        Example:
            >>> calc = GuestCalculator()
            >>> results = calc.batch_create_from_identifiers(
            ...     ["50-78-2", "58-08-2", "aspirin"], mark_in_inventory=True
            ... )
            >>> print(f"{len(results['created'])} created, {len(results['matched'])} matched, {len(results['failed'])} failed")
        """
        logger.info(f"Batch creating {len(identifiers)} guest(s) from identifiers, mark_in_inventory={mark_in_inventory}")

        created: List[Guest] = []
        matched: List[Guest] = []
        cas_filled: List[Guest] = []
        failed: List[dict] = []

        for identifier in identifiers:
            identifier = identifier.strip()
            if not identifier:
                continue

            try:
                compound = pubchem_client.fetch_compound(identifier)
                if compound is None:
                    logger.warning(f"Could not resolve '{identifier}' on PubChem")
                    failed.append({"identifier": identifier, "error": "not found on PubChem"})
                    continue

                existing = None
                if compound["cas_number"]:
                    existing = queries.get_guest_by_cas(self.conn, compound["cas_number"])
                if existing is None and compound["smiles"]:
                    existing = queries.get_guest_by_smiles(self.conn, compound["smiles"])

                if existing:
                    guest = existing
                    matched.append(guest)
                    logger.debug(f"'{identifier}' already exists as guest '{guest.name}'")

                    if compound["cas_number"] and not guest.cas_number:
                        queries.update_guest_cas(self.conn, guest.id, compound["cas_number"])
                        guest.cas_number = compound["cas_number"]
                        cas_filled.append(guest)
                        logger.info(f"Backfilled CAS number for '{guest.name}' from '{identifier}'")
                else:
                    guest = self.create_guest(
                        name=compound["name"],
                        smiles=compound["smiles"],
                        molecular_weight=compound["molecular_weight"],
                        iupac_name=compound["iupac_name"],
                        molecular_formula=compound["formula"],
                        pubchem_cid=compound["cid"],
                        cas_number=compound["cas_number"],
                    )
                    created.append(guest)

                if mark_in_inventory and not guest.in_inventory:
                    queries.update_guest_inventory(self.conn, guest.id, True)
                    guest.in_inventory = True

            except Exception as e:
                logger.warning(f"Failed to process identifier '{identifier}': {e}")
                failed.append({"identifier": identifier, "error": str(e)})

        logger.info(
            f"Batch create complete: {len(created)} created, "
            f"{len(matched)} matched existing ({len(cas_filled)} CAS-backfilled), {len(failed)} failed"
        )
        return {"created": created, "matched": matched, "cas_filled": cas_filled, "failed": failed}

    def set_inventory(self, guest_id: int, in_inventory: bool) -> Optional[Guest]:
        """
        Mark whether a guest is currently in our physical inventory.

        Distinct from pricing/vendor availability: a guest can be
        purchasable from a vendor without us actually having it on hand.
        """
        logger.debug(f"Setting inventory status for guest ID {guest_id}: in_inventory={in_inventory}")
        guest = queries.get_guest_by_id(self.conn, guest_id)

        if not guest:
            logger.warning(f"Guest with ID {guest_id} not found")
            return None

        queries.update_guest_inventory(self.conn, guest_id, in_inventory)
        logger.info(f"Set '{guest.name}' inventory status to {in_inventory}")
        return queries.get_guest_by_id(self.conn, guest_id)

    def delete_guest(self, guest_id: int) -> bool:
        """Delete a guest from the database."""
        logger.debug(f"Deleting guest with ID: {guest_id}")

        guest = queries.get_guest_by_id(self.conn, guest_id)

        if guest:
            queries.delete_guest(self.conn, guest_id)
            logger.info(f"Deleted guest '{guest.name}'")
            return True

        logger.warning(f"Guest with ID {guest_id} not found")
        return False

    def close(self):
        """Close database connection."""
        logger.debug("Closing GuestCalculator connection")
        close_connection()

    # ==================== FILE IMPORTS ====================

    def import_from_xml(self, xml_file: str) -> List[Guest]:
        """
        Import guests from XML file.

        Expected XML structure:
            <guests>
                <guest>
                    <name>Aspirin</name>
                    <smiles>CC(=O)OC1=CC=CC=C1C(=O)O</smiles>
                    <molecular_weight>180.16</molecular_weight>
                    <iupac_name>2-acetyloxybenzoic acid</iupac_name>
                    <molecular_formula>C9H8O4</molecular_formula>
                    <cas_number>50-78-2</cas_number>
                    <physical_state>solid</physical_state>
                </guest>
                ...
            </guests>

        Args:
            xml_file: Path to XML file

        Returns:
            List[Guest]: Created guest objects

        Raises:
            FileNotFoundError: If XML file doesn't exist
            ValueError: If XML is malformed
        """
        logger.debug(f"Importing guests from XML file: {xml_file}")
        xml_path = Path(xml_file)

        if not xml_path.exists():
            logger.error(f"XML file not found: {xml_file}")
            raise FileNotFoundError(f"XML file not found: {xml_file}")

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            created_guests = []

            for guest_elem in root.findall('guest'):
                try:
                    guest_data = {
                        'name': guest_elem.findtext('name', '').strip(),
                        'smiles': guest_elem.findtext('smiles', '').strip(),
                        'molecular_weight': self._parse_float(guest_elem.findtext('molecular_weight')),
                        'iupac_name': guest_elem.findtext('iupac_name', '').strip() or None,
                        'molecular_formula': guest_elem.findtext('molecular_formula', '').strip() or None,
                        'cas_number': guest_elem.findtext('cas_number', '').strip() or None,
                        'physical_state': guest_elem.findtext('physical_state', '').strip() or None,
                    }

                    # Validate required fields
                    if not guest_data['name'] or not guest_data['smiles']:
                        logger.warning("Skipping guest with missing name or SMILES")
                        continue

                    guest = self.create_guest(**guest_data)
                    created_guests.append(guest)

                except ValueError as e:
                    logger.warning(f"Failed to create guest from XML: {e}")
                    continue

            logger.info(f"Imported {len(created_guests)} guest(s) from XML")
            return created_guests

        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise ValueError(f"Failed to parse XML: {e}")

    def import_from_csv(self, csv_file: str) -> List[Guest]:
        """
        Import guests from CSV file.

        Expected CSV columns:
            name, smiles, molecular_weight, iupac_name, molecular_formula, cas_number, physical_state

        Args:
            csv_file: Path to CSV file

        Returns:
            List[Guest]: Created guest objects

        Raises:
            FileNotFoundError: If CSV file doesn't exist
        """
        logger.debug(f"Importing guests from CSV file: {csv_file}")
        csv_path = Path(csv_file)

        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_file}")
            raise FileNotFoundError(f"CSV file not found: {csv_file}")

        created_guests = []

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, start=2):
                    try:
                        guest_data = {
                            'name': row.get('name', '').strip(),
                            'smiles': row.get('smiles', '').strip(),
                            'molecular_weight': self._parse_float(row.get('molecular_weight')),
                            'iupac_name': row.get('iupac_name', '').strip() or None,
                            'molecular_formula': row.get('molecular_formula', '').strip() or None,
                            'cas_number': row.get('cas_number', '').strip() or None,
                            'physical_state': row.get('physical_state', '').strip() or None,
                        }

                        # Validate required fields
                        if not guest_data['name'] or not guest_data['smiles']:
                            logger.warning(f"Row {row_num}: Skipping guest with missing name or SMILES")
                            continue

                        guest = self.create_guest(**guest_data)
                        created_guests.append(guest)

                    except ValueError as e:
                        logger.warning(f"Row {row_num}: Failed to create guest: {e}")
                        continue

            logger.info(f"Imported {len(created_guests)} guest(s) from CSV")
            return created_guests

        except csv.Error as e:
            logger.error(f"Failed to parse CSV: {e}")
            raise ValueError(f"Failed to parse CSV: {e}")

    def import_from_json(self, json_file: str) -> List[Guest]:
        """
        Import guests from JSON file.

        Expected JSON structure:
            [
                {
                    "name": "Aspirin",
                    "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "molecular_weight": 180.16,
                    "iupac_name": "2-acetyloxybenzoic acid",
                    "molecular_formula": "C9H8O4",
                    "cas_number": "50-78-2",
                    "physical_state": "solid"
                },
                ...
            ]

        Args:
            json_file: Path to JSON file

        Returns:
            List[Guest]: Created guest objects

        Raises:
            FileNotFoundError: If JSON file doesn't exist
            ValueError: If JSON is malformed
        """
        logger.debug(f"Importing guests from JSON file: {json_file}")
        json_path = Path(json_file)

        if not json_path.exists():
            logger.error(f"JSON file not found: {json_file}")
            raise FileNotFoundError(f"JSON file not found: {json_file}")

        created_guests = []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.error("JSON must contain an array of guest objects")
                raise ValueError("JSON must contain an array of guest objects")

            for guest_data in data:
                try:
                    guest = self.create_guest(
                        name=guest_data.get('name'),
                        smiles=guest_data.get('smiles'),
                        molecular_weight=guest_data.get('molecular_weight'),
                        iupac_name=guest_data.get('iupac_name'),
                        molecular_formula=guest_data.get('molecular_formula'),
                        cas_number=guest_data.get('cas_number'),
                        physical_state=guest_data.get('physical_state'),
                    )
                    created_guests.append(guest)

                except ValueError as e:
                    logger.warning(f"Failed to create guest from JSON: {e}")
                    continue

            logger.info(f"Imported {len(created_guests)} guest(s) from JSON")
            return created_guests

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise ValueError(f"Failed to parse JSON: {e}")

    def import_from_file(self, file_path: str) -> List[Guest]:
        """
        Auto-detect file format and import.

        Supports: XML, CSV, JSON

        Args:
            file_path: Path to file

        Returns:
            List[Guest]: Created guest objects

        Example:
            >>> calc = GuestCalculator()
            >>> guests = calc.import_from_file('guests.xml')
            >>> guests = calc.import_from_file('guests.csv')
            >>> guests = calc.import_from_file('guests.json')
        """
        logger.debug(f"Importing guests from file: {file_path}")
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.xml':
            logger.debug("File identified as XML file")
            return self.import_from_xml(file_path)
        elif file_ext == '.csv':
            logger.debug("File identified as CSV file")
            return self.import_from_csv(file_path)
        elif file_ext == '.json':
            logger.debug("File identified as JSON file")
            return self.import_from_json(file_path)
        else:
            logger.error(f"Unsupported file format: {file_ext}")
            raise ValueError(f"Unsupported file format: {file_ext}")

    # ==================== UTILITIES ====================

    @staticmethod
    def _parse_float(value: Optional[str]) -> Optional[float]:
        """Safely parse float value."""
        if not value or (isinstance(value, str) and value.strip() == ''):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
