from pathlib import Path
import json
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class VotingRecord(BaseModel):
    round: int
    voted_for: str

class Cardinal(BaseModel):
    name: str
    bio_file: Path
    voting_history_file: Path
    political_leaning: float  # -1.0 (very conservative) to 1.0 (very liberal)
    bio: str = Field(default="")
    voting_history: List[VotingRecord] = Field(default_factory=list)
    
    def model_post_init(self, __context) -> None:
        """Initialize additional fields after model validation."""
        self.bio = self._load_bio()
        self.voting_history = self._load_voting_history()

    def _load_bio(self) -> str:
        """Load the cardinal's biographical information."""
        with open(self.bio_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _load_voting_history(self) -> List[VotingRecord]:
        """Load the cardinal's voting history."""
        if not self.voting_history_file.exists():
            return []
        
        with open(self.voting_history_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
            return [VotingRecord(**record) for record in records]

    def save_vote(self, round_number: int, voted_for: str):
        """Save the cardinal's vote to their voting history file."""
        record = VotingRecord(
            round=round_number,
            voted_for=voted_for
        )
        
        self.voting_history.append(record)
        
        # Save to file
        with open(self.voting_history_file, 'w', encoding='utf-8') as f:
            json.dump(
                [record.model_dump() for record in self.voting_history],
                f,
                indent=2
            )