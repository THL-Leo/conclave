from pathlib import Path
from typing import List, Dict, Optional, Set, Union
from cardinal import Cardinal
from round_results import RoundResults, RoundResult
import json
import logging
import openai
from dotenv import load_dotenv
import os
import requests
import argparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LLMConfig:
    def __init__(self, 
                 provider: str = "openai",  # "openai" or "local"
                 local_url: str = "http://127.0.0.1:1234",
                 model: str = "gpt-4-turbo-preview",
                 temperature: float = 0.4):
        self.provider = provider
        self.local_url = local_url
        self.model = model
        self.temperature = temperature
        
        # Initialize client if using OpenAI
        if provider == "openai":
            self.client = openai.OpenAI()
        else:
            self.client = None

    async def get_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Get completion from either OpenAI or local endpoint."""
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature
            )
            return response.choices[0].message.content.strip()
        else:
            # Local LLM API call
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": self.temperature,
                "stream": False
            }
            
            try:
                response = requests.post(f"{self.local_url}/v1/chat/completions", json=payload)
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Error calling local LLM: {e}")
                raise

class Conclave:
    def __init__(self, cardinals_data_path: Path, llm_config: Optional[LLMConfig] = None):
        """
        Initialize the conclave simulation.
        
        Args:
            cardinals_data_path: Path to the JSON file containing cardinal information
            llm_config: Configuration for LLM provider (OpenAI or local)
        """
        self.cardinals: List[Cardinal] = self._load_cardinals(cardinals_data_path)
        self.round_number = 0
        self.pope_elected = False
        self.winner: Optional[str] = None
        self.frontrunners: Dict[str, float] = {}  # Cardinal name to support ratio
        self.round_results = RoundResults(cardinals_data_path.parent)
        self.llm_config = llm_config or LLMConfig()  # Default to OpenAI if not specified

    def _load_cardinals(self, cardinals_data_path: Path) -> List[Cardinal]:
        """Load cardinal information from JSON file."""
        with open(cardinals_data_path, 'r', encoding='utf-8') as f:
            cardinals_data = json.load(f)
            
        return [
            Cardinal(
                name=data['name'],
                bio_file=Path(data['bio_file']),
                voting_history_file=Path(data['voting_history_file']),
                political_leaning=data['political_leaning']
            )
            for data in cardinals_data
        ]

    def _update_frontrunners(self, votes: Dict[str, int]):
        """Update the list of frontrunners based on voting results."""
        total_votes = sum(votes.values())
        
        # Calculate support ratio for each cardinal
        support_ratios = {
            name: count / total_votes 
            for name, count in votes.items()
        }
        
        # Update frontrunners (keep those with more than 15% support)
        self.frontrunners = {
            name: ratio 
            for name, ratio in support_ratios.items() 
            if ratio > 0.15
        }

    def _get_voting_prompt(self, cardinal: Cardinal, eligible_cardinals: List[str]) -> str:
        """
        Construct a detailed prompt for the voting decision.
        """
        # Get previous round results if available
        previous_round = self.round_results.get_round_result(self.round_number - 1)
        
        prompt = f"""You are Cardinal {cardinal.name} participating in the 2025 papal conclave.

                    Your biographical information and political stance:
                    {cardinal.bio}

                    Political leaning score: {cardinal.political_leaning} (-1.0 is very conservative, 1.0 is very liberal)

                    Current state of the conclave:
                    - Round: {self.round_number}
                    - Frontrunners and their support from previous round:
                    """
        
        if self.frontrunners:
            for name, support in self.frontrunners.items():
                prompt += f"  * {name}: {support*100:.1f}% support\n"
        else:
            prompt += "  * No clear frontrunners yet\n"

        if previous_round:
            prompt += "\nPrevious round results:\n"
            for name, votes in previous_round.votes.items():
                prompt += f"  * {name}: {votes} votes\n"
            
            if cardinal.voting_history:
                last_vote = cardinal.voting_history[-1]
                prompt += f"\nYou previously voted for: {last_vote.voted_for}\n"

        prompt += "\nEligible cardinals to vote for:\n"
        for name in eligible_cardinals:
            prompt += f"- {name}\n"

        prompt += """
                Based on:
                1. Your own political leaning and biographical background
                2. The current frontrunners and their support
                3. The previous round's results (if any)
                4. Your previous vote (if any)
                5. The need for a pope who can lead the Church effectively
                6. You are more likely to vote for a cardinal who is from the same continent as you or speaks the same language as you or shares the same political views as you
                7. You do not want to vote for someone who is too old or too young
                8. You don't want a candidate with a history of scandal or controversy

                Which cardinal do you vote for? Please respond with ONLY the name of the cardinal you're voting for, 
                do not include the word Cardinal, exactly as it appears in the eligible cardinals list. 
                The response should just be the name of the cardinal that appeared in the eligible cardinals list. 
                Do not include any other text or comments.
                """

        return prompt

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison by removing diacritics and special spaces."""
        import unicodedata
        # Normalize unicode characters and convert to NFKD form
        name = unicodedata.normalize('NFKD', name)
        # Remove diacritics
        name = ''.join(c for c in name if not unicodedata.combining(c))
        # Replace special spaces and multiple spaces with single space
        name = ' '.join(name.split())
        return name.lower()

    def _find_matching_cardinal(self, voted_name: str) -> Optional[str]:
        """Find the exact cardinal name from the list that matches the voted name."""
        normalized_vote = self._normalize_name(voted_name)
        for cardinal in self.cardinals:
            if self._normalize_name(cardinal.name) == normalized_vote:
                return cardinal.name
        return None

    async def run_voting_round(self) -> Dict[str, int]:
        """
        Run a single round of voting in the conclave.
        
        Returns:
            Dict mapping cardinal names to the number of votes they received
        """
        self.round_number += 1
        logger.info(f"\nStarting round {self.round_number}")
        
        # Get list of eligible cardinals
        eligible_cardinals = [cardinal.name for cardinal in self.cardinals]
        
        # Collect votes from all cardinals
        votes: Dict[str, int] = {}
        total_cardinals = len(self.cardinals)
        
        for idx, cardinal in enumerate(self.cardinals, 1):
            logger.info(f"[{idx}/{total_cardinals}] Cardinal {cardinal.name} is voting...")
            
            # Construct the prompt for this cardinal's vote
            prompt = self._get_voting_prompt(cardinal, eligible_cardinals)
            
            try:
                # Get the cardinal's vote using configured LLM
                voted_for_raw = await self.llm_config.get_completion(
                    "You are simulating a cardinal in the 2025 papal conclave.",
                    prompt
                )
                
                # Find the matching cardinal name from the eligible list
                voted_for = self._find_matching_cardinal(voted_for_raw)
                
                # Validate and record the vote
                if voted_for in eligible_cardinals:
                    votes[voted_for] = votes.get(voted_for, 0) + 1
                    # Save only the cardinal's individual vote
                    cardinal.save_vote(self.round_number, voted_for)
                    logger.info(f"✓ Cardinal {cardinal.name} has voted for {voted_for}")
                else:
                    logger.warning(f"Invalid vote from {cardinal.name}: {voted_for_raw}")
                    logger.warning("Could not match vote to any eligible cardinal name")
                    # If invalid vote, choose their previous vote or a frontrunner
                    if cardinal.voting_history:
                        voted_for = cardinal.voting_history[-1].voted_for
                    elif self.frontrunners:
                        voted_for = max(self.frontrunners.items(), key=lambda x: x[1])[0]
                    else:
                        import random
                        voted_for = random.choice(eligible_cardinals)
                    votes[voted_for] = votes.get(voted_for, 0) + 1
                    cardinal.save_vote(self.round_number, voted_for)
                    logger.info(f"✓ Cardinal {cardinal.name} has voted for {voted_for} (fallback vote)")

            except Exception as e:
                logger.error(f"Error getting vote from {cardinal.name}: {e}")
                # In case of error, use previous vote or random choice
                if cardinal.voting_history:
                    voted_for = cardinal.voting_history[-1].voted_for
                else:
                    import random
                    voted_for = random.choice(eligible_cardinals)
                votes[voted_for] = votes.get(voted_for, 0) + 1
                cardinal.save_vote(self.round_number, voted_for)
                logger.info(f"✓ Cardinal {cardinal.name} has voted (error fallback)")
        
        # After all votes are collected, save the round results
        required_votes = (len(self.cardinals) * 2 // 3) + 1
        winner = None
        for cardinal_name, vote_count in votes.items():
            if vote_count >= required_votes:
                winner = cardinal_name
                self.pope_elected = True
                self.winner = cardinal_name
                break

        round_result = RoundResult(
            round_number=self.round_number,
            votes=votes,
            winner=winner
        )
        self.round_results.save_round_result(round_result)
        
        # Update frontrunners based on this round's votes
        self._update_frontrunners(votes)
        
        # Log the results
        logger.info(f"\nRound {self.round_number} results:")
        for name, vote_count in sorted(votes.items(), key=lambda x: x[1], reverse=True):
            percentage = (vote_count / len(self.cardinals)) * 100
            logger.info(f"{name}: {vote_count} votes ({percentage:.1f}%)")
        
        if winner:
            logger.info(f"\nCardinal {winner} has been elected Pope!")
                
        return votes

    async def run_simulation(self, max_rounds: int = 30) -> Optional[str]:
        """Run the complete conclave simulation."""
        while not self.pope_elected and self.round_number < max_rounds:
            await self.run_voting_round()
            
        return self.winner

if __name__ == "__main__":
    import asyncio
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run papal conclave simulation')
    parser.add_argument('--local', action='store_true', help='Use local LLM endpoint (default: use OpenAI)')
    parser.add_argument('--url', type=str, default='http://127.0.0.1:1234', help='Local LLM endpoint URL')
    parser.add_argument('--temperature', type=float, default=0.4, help='Temperature for LLM sampling')
    args = parser.parse_args()
    
    # Example usage
    cardinals_data_path = Path("data/cardinals.json")
    
    # Configure LLM based on arguments
    llm_config = LLMConfig(
        provider="local" if args.local else "openai",
        local_url=args.url,
        temperature=args.temperature
    )
    
    # Create conclave with config
    conclave = Conclave(cardinals_data_path, llm_config)
    
    # Run simulation
    elected_pope = asyncio.run(conclave.run_simulation())
    
    if elected_pope:
        print(f"\nConclave has elected {elected_pope} as the new Pope!")
    else:
        print("\nConclave failed to elect a new Pope.") 