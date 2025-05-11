from pathlib import Path
import json
from typing import Dict, Optional
from pydantic import BaseModel

class RoundResult(BaseModel):
    round_number: int
    votes: Dict[str, int]  # Cardinal name to number of votes received
    winner: Optional[str] = None
    
class RoundResults:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.results_dir = data_dir / "round_results"
        self.results_dir.mkdir(exist_ok=True)
    
    def save_round_result(self, round_result: RoundResult):
        """Save the results of a voting round."""
        file_path = self.results_dir / f"round_{round_result.round_number}_results.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(round_result.model_dump(), f, indent=2)
    
    def get_round_result(self, round_number: int) -> Optional[RoundResult]:
        """Get the results of a specific round."""
        file_path = self.results_dir / f"round_{round_number}_results.json"
        if not file_path.exists():
            return None
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return RoundResult(**data)
    
    def get_latest_round_result(self) -> Optional[RoundResult]:
        """Get the results of the most recent round."""
        result_files = list(self.results_dir.glob("round_*_results.json"))
        if not result_files:
            return None
            
        latest_file = max(result_files, key=lambda p: int(p.stem.split('_')[1]))
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return RoundResult(**data) 