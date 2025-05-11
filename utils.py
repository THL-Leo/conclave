from pathlib import Path
import json
from typing import Dict, List
import shutil

def create_cardinal_data_structure(
    name: str,
    bio_text: str,
    political_leaning: float,
    data_dir: Path = Path("data")
) -> Dict:
    """
    Create the necessary files and data structure for a new cardinal.
    
    Args:
        name: Name of the cardinal
        bio_text: Biographical text for the cardinal
        political_leaning: Float between -1.0 (very conservative) and 1.0 (very liberal)
        data_dir: Directory to store cardinal data
        
    Returns:
        Dictionary containing the cardinal's information
    """
    # Create data directory if it doesn't exist
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create bio file
    bio_file = data_dir / f"{name.lower().replace(' ', '_')}_bio.txt"
    with open(bio_file, 'w', encoding='utf-8') as f:
        f.write(bio_text)
    
    # Create empty voting history file
    voting_history_file = data_dir / f"{name.lower().replace(' ', '_')}_voting_history.json"
    if not voting_history_file.exists():
        with open(voting_history_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    return {
        "name": name,
        "bio_file": str(bio_file),
        "voting_history_file": str(voting_history_file),
        "political_leaning": political_leaning
    }

def save_cardinals_data(cardinals: List[Dict], data_dir: Path = Path("data")):
    """
    Save cardinal information to a JSON file.
    
    Args:
        cardinals: List of cardinal dictionaries
        data_dir: Directory to store the data
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    cardinals_file = data_dir / "cardinals.json"
    
    with open(cardinals_file, 'w', encoding='utf-8') as f:
        json.dump(cardinals, f, indent=2)

def clear_voting_history(data_dir: Path = Path("data")):
    """
    Clear all voting history files to start a fresh simulation.
    
    Args:
        data_dir: Directory containing the data files
    """
    for file in data_dir.glob("*_voting_history.json"):
        with open(file, 'w', encoding='utf-8') as f:
            json.dump([], f)

def backup_simulation_data(data_dir: Path = Path("data"), backup_suffix: str = "backup"):
    """
    Create a backup of all simulation data.
    
    Args:
        data_dir: Directory containing the data files
        backup_suffix: Suffix to add to the backup directory name
    """
    backup_dir = data_dir.parent / f"{data_dir.name}_{backup_suffix}"
    shutil.copytree(data_dir, backup_dir, dirs_exist_ok=True) 