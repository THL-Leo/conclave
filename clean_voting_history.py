from pathlib import Path
import json

def clean_voting_history_file(file_path: Path) -> None:
    """Clear all content from a voting history JSON file."""
    try:
        # Write an empty array to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
        print(f"Cleared {file_path.name}")
    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")

def main():
    data_dir = Path('data')
    
    # Process all voting history JSON files
    for file_path in data_dir.glob('*_voting_history.json'):
        clean_voting_history_file(file_path)

if __name__ == '__main__':
    main() 