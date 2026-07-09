"""
Calculate guest properties, import from files, and manage database operations.
    
Volumes calculated from SMILES using RDKit's ComputeMolVolume()

Supported Import Formats:
    - XML
    - CSV
    - JSON
"""

import logging
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List
from rdkit import Chem
from rdkit.Chem import AllChem
from supramatch.db import queries
from supramatch.db.database import get_connection, close_connection
from supramatch.models.guest import Guest
from supramatch.config import GUEST_CALC_CONFIG
from supramatch.utils.helpers import format_volume, format_price

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
    
    # ==================== DATABASE OPERATIONS ====================

    def create_guest(
        self,
        name: str,
        smiles: str,
        molar_mass: float = None,
        cas_number: str = None,
        supplier: str = None,
        price_per_gram: float = None,
        physical_state: str = None,
        url: str = None
    ) -> Guest:
        """
        Create a new guest molecule in the database with calculated properties.
        
        Args:
            name: Common name of the molecule.
            smiles: SMILES string.
            molar_mass: Molar mass in g/mol.
            cas_number: CAS registry number.
            supplier: Supplier name (e.g., 'Sigma-Aldrich').
            price_per_gram: Price in USD per gram ($/g).
            physical_state: 'solid', 'liquid', or 'gas'.
            url: Product URL.
        
        Returns:
            Guest: The created guest object.
        
        Raises:
            ValueError: If guest already exists, SMILES invalid, or calculation fails.
        
        Example:
            >>> calc = GuestCalculator()
            >>> guest = calc.create_guest(
            ...     name='Benzene',
            ...     smiles='c1ccccc1',
            ...     price_per_gram=0.59,
            ...     supplier='Sigma-Aldrich'
            ... )
            >>> print(f"Created: {guest.name}")
            >>> print(f"Volume: {guest.molecular_volume:.2f} Å³")
            >>> print(f"Price: ${guest.price_per_gram:.2f}/g")
        """
        logger.info(f"Creating guest: {name}")
        logger.debug(f"SMILES: {smiles}, CAS: {cas_number}")
        
        if not name or not isinstance(name, str):
            logger.error("Name must be a non-empty string")
            raise ValueError("Name must be a non-empty string")
        
        if not smiles or not isinstance(smiles, str):
            logger.error("SMILES must be a non-empty string")
            raise ValueError("SMILES must be a non-empty string")
        
        # Check if guest already exists by CAS number or name
        if cas_number:
            existing = queries.get_guest_by_cas(self.conn, cas_number)
            if existing:
                logger.warning(f"Guest with CAS number '{cas_number}' already exists in database")
                raise ValueError(f"Guest with CAS number '{cas_number}' already exists in database")

        existing = queries.get_guest_by_name(self.conn, name)
        if existing:
            logger.warning(f"Guest with name '{name}' already exists in database")
            raise ValueError(f"Guest with name '{name}' already exists in database")
        
        # Validate molar mass
        if molar_mass is not None and molar_mass < 0:
            logger.error("Molar mass cannot be negative")
            raise ValueError("Molar mass cannot be negative")

        # Validate price
        if price_per_gram is not None and price_per_gram < 0:
            logger.error("Price cannot be negative")
            raise ValueError("Price cannot be negative")
        
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

            # Create guest record
            guest = queries.create_guest(
                self.conn,
                name=name,
                smiles=smiles,
                molecular_volume=molecular_volume,
                molar_mass=molar_mass,
                cas_number=cas_number,
                supplier=supplier,
                price_per_gram=price_per_gram,
                physical_state=physical_state.lower() if physical_state else None,
                url=url,
            )

            logger.info(f"Created guest '{name}': Volume={volume_str}")
            return guest

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to create guest {name}: {e}", exc_info=True)
            raise

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

    def search_guests(self, name_pattern: str = None, supplier: str = None) -> List[Guest]:
        """Search for guests with flexible criteria."""
        logger.debug(f"Searching for guests: name_pattern={name_pattern}, supplier={supplier}")
        return queries.search_guests(self.conn, name_pattern=name_pattern, supplier=supplier)

    def list_guests(self, limit: int = None, offset: int = 0) -> List[Guest]:
        """Get all guests from the database with optional pagination."""
        logger.debug("Retrieving all guests from database")
        guests = queries.list_guests(self.conn, limit=limit, offset=offset)
        logger.info(f"Found {len(guests)} guest(s) in database")
        return guests

    def update_guest_price(self, guest_id: int, new_price_per_gram: float) -> bool:
        """Update guest price without recalculating properties."""
        logger.debug(f"Updating price for guest ID: {guest_id}")

        if new_price_per_gram < 0:
            logger.error("Price cannot be negative")
            raise ValueError("Price cannot be negative")

        guest = queries.get_guest_by_id(self.conn, guest_id)

        if guest:
            logger.info(f"Updating price for {guest.name}")
            old_price_str = format_price(guest.price_per_gram)
            queries.update_guest_price(self.conn, guest_id, new_price_per_gram)
            new_price_str = format_price(new_price_per_gram)
            logger.info(f"Updated {guest.name} price from {old_price_str} to {new_price_str}")
            return True

        logger.warning(f"Guest with ID {guest_id} not found")
        return False

    def update_guest_url(self, guest_id: int, url: str) -> bool:
        """Update guest supplier URL."""
        logger.debug(f"Updating URL for guest ID: {guest_id}")
        guest = queries.get_guest_by_id(self.conn, guest_id)

        if guest:
            logger.info(f"Updating URL for {guest.name}")
            old_url = guest.url
            queries.update_guest_url(self.conn, guest_id, url)
            logger.info(f"Updated {guest.name} URL from {old_url} to {url}")
            return True

        logger.warning(f"Guest with ID {guest_id} not found")
        return False

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
                    <name>Benzene</name>
                    <smiles>c1ccccc1</smiles>
                    <molar_mass>78.11<molar_mass>
                    <cas_number>71-43-2</cas_number>
                    <supplier>Sigma-Aldrich</supplier>
                    <price_per_gram>0.59</price_per_gram>
                    <physical_state>liquid</physical_state>
                    <url>https://...</url>
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
                        'molar_mass': self._parse_float(guest_elem.findtext('molar_mass')),
                        'cas_number': guest_elem.findtext('cas_number', '').strip() or None,
                        'supplier': guest_elem.findtext('supplier', '').strip() or None,
                        'price_per_gram': self._parse_float(guest_elem.findtext('price_per_gram')),
                        'physical_state': guest_elem.findtext('physical_state', '').strip() or None,
                        'url': guest_elem.findtext('url', '').strip() or None,
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
            name, smiles, molar_mass, cas_number, supplier, price_per_gram, physical_state, url
        
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
                            'molar_mass': self._parse_float(row.get('molar_mass')),
                            'cas_number': row.get('cas_number', '').strip() or None,
                            'supplier': row.get('supplier', '').strip() or None,
                            'price_per_gram': self._parse_float(row.get('price_per_gram')),
                            'physical_state': row.get('physical_state', '').strip() or None,
                            'url': row.get('url', '').strip() or None,
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
                    "name": "Benzene",
                    "smiles": "c1ccccc1",
                    "molar_mass": 78.11,
                    "cas_number": "71-43-2",
                    "supplier": "Sigma-Aldrich",
                    "price_per_gram": 0.59,
                    "physical_state": "liquid",
                    "url": "https://..."
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
                        molar_mass=guest_data.get('molar_mass'),
                        cas_number=guest_data.get('cas_number'),
                        supplier=guest_data.get('supplier'),
                        price_per_gram=guest_data.get('price_per_gram'),
                        physical_state=guest_data.get('physical_state'),
                        url=guest_data.get('url'),
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