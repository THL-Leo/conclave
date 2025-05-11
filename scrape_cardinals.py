import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import re
from utils import create_cardinal_data_structure, save_cardinals_data
import openai
from dotenv import load_dotenv
import os
import argparse

# Load environment variables
load_dotenv()

class LLMConfig:
    def __init__(self, 
                 provider: str = "openai",  # "openai" or "local"
                 local_url: str = "http://127.0.0.1:1234",
                 model: str = "gpt-4-turbo-preview",
                 temperature: float = 0.3):
        self.provider = provider
        self.local_url = local_url
        self.model = model
        self.temperature = temperature
        
        # Initialize client if using OpenAI
        if provider == "openai":
            self.client = openai.OpenAI()
        else:
            self.client = None

    def get_completion(self, system_prompt: str, user_prompt: str) -> str:
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
                print(f"Error calling local LLM: {e}")
                raise

def save_political_summary(data_dir: Path, leanings: List[float]):
    """
    Save the political leaning summary to a file.
    """
    summary_file = data_dir / "political_leaning_summaries.txt"
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("Political Leaning Summary:\n")
        f.write(f"Average leaning: {sum(leanings) / len(leanings):.2f}\n")
        f.write(f"Most conservative: {min(leanings):.2f}\n")
        f.write(f"Most liberal: {max(leanings):.2f}\n\n")
        
        # Distribution
        ranges = {
            "Very Conservative (-1.0 to -0.6)": 0,
            "Conservative (-0.6 to -0.2)": 0,
            "Moderate (-0.2 to 0.2)": 0,
            "Liberal (0.2 to 0.6)": 0,
            "Very Liberal (0.6 to 1.0)": 0
        }
        
        for leaning in leanings:
            if leaning < -0.6:
                ranges["Very Conservative (-1.0 to -0.6)"] += 1
            elif leaning < -0.2:
                ranges["Conservative (-0.6 to -0.2)"] += 1
            elif leaning < 0.2:
                ranges["Moderate (-0.2 to 0.2)"] += 1
            elif leaning < 0.6:
                ranges["Liberal (0.2 to 0.6)"] += 1
            else:
                ranges["Very Liberal (0.6 to 1.0)"] += 1
        
        f.write("Distribution of political leanings:\n")
        for range_name, count in ranges.items():
            percentage = (count / len(leanings)) * 100
            f.write(f"{range_name}: {count} cardinals ({percentage:.1f}%)\n")
    
    print(f"\nPolitical leaning summary saved to {summary_file}")

def get_political_leaning(bio_text: str, llm_config: LLMConfig) -> Tuple[float, str]:
    """
    Use LLM to analyze the cardinal's political leaning.
    Returns a tuple of (score, explanation)
    -1.0 (very conservative) to 1.0 (very liberal)
    """
    prompt = f"""Analyze the following biographical text of a Catholic cardinal and determine their political leaning within the Church context.
                Consider factors such as:
                - Their stance on Church doctrine and tradition
                - Views on social issues and reform
                - Approach to pastoral care
                - Position on Church governance
                - Engagement with contemporary issues
                - Theological positions

                Text to analyze:
                {bio_text}

                Please provide:
                1. A political leaning score from -1.0 (very conservative/traditionalist) to 1.0 (very liberal/progressive)
                2. A brief explanation of your reasoning

                Format your response exactly as follows:
                SCORE: [number between -1.0 and 1.0]
                EXPLANATION: [your explanation]"""

    try:
        result = llm_config.get_completion(
            "You are an expert analyst of Catholic Church politics and theology.",
            prompt
        )
        
        # Extract score and explanation
        score_match = re.search(r'SCORE:\s*([-\d.]+)', result)
        explanation_match = re.search(r'EXPLANATION:\s*(.+)', result, re.DOTALL)
        
        if score_match and explanation_match:
            score = float(score_match.group(1))
            explanation = explanation_match.group(1).strip()
            # Ensure score is within bounds
            score = max(min(score, 1.0), -1.0)
            return score, explanation
        else:
            return 0.0, "Error parsing LLM response"
            
    except Exception as e:
        print(f"Error in LLM analysis: {e}")
        return 0.0, f"Error in analysis: {str(e)}"

def scrape_cardinal_bio(name: str, wikipedia_url: Optional[str] = None) -> str:
    """
    Scrape biographical information for a cardinal from Wikipedia.
    """
    if not wikipedia_url:
        # Convert name to Wikipedia URL format
        wiki_name = name.replace(" ", "_")
        wikipedia_url = f"https://en.wikipedia.org/wiki/{wiki_name}"
    
    try:
        response = requests.get(wikipedia_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get the first few paragraphs of content
        content = []
        for p in soup.find_all('p'):
            if len(content) < 5 and p.text.strip():  # Get first 5 non-empty paragraphs
                content.append(p.text.strip())
        
        bio = "\n".join(content)
        
        # Clean up the text
        bio = re.sub(r'\[\d+\]', '', bio)  # Remove reference numbers
        bio = re.sub(r'\s+', ' ', bio)  # Normalize whitespace
        
        return bio if bio else f"No biographical information found for {name}"
        
    except Exception as e:
        print(f"Error scraping bio for {name}: {e}")
        return f"Error retrieving biographical information for {name}"

def process_cardinals(llm_config: Optional[LLMConfig] = None):
    """
    Process cardinal data from the 2025 conclave and create data files.
    """
    # Use default OpenAI config if none provided
    if llm_config is None:
        llm_config = LLMConfig()

    # Create data directory
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Load cardinals from cardinal_list.json
    try:
        with open(data_dir / "cardinal_list.json", 'r', encoding='utf-8') as f:
            cardinals_data = json.load(f)
    except FileNotFoundError:
        print("Error: cardinal_list.json not found. Please run parse_wiki_cardinals.py first.")
        return
    
    processed_cardinals = []
    total_cardinals = len(cardinals_data)
    
    for idx, cardinal in enumerate(cardinals_data, 1):
        print(f"Processing cardinal {idx}/{total_cardinals}: {cardinal['name']}...")
        
        # Scrape biographical information
        bio = scrape_cardinal_bio(cardinal['name'], cardinal.get('wiki_url'))
        
        # Analyze political leaning using configured LLM
        political_leaning, explanation = get_political_leaning(bio, llm_config)
        
        # Create cardinal data structure with additional information
        cardinal_data = create_cardinal_data_structure(
            name=cardinal['name'],
            bio_text=f"{bio}\n\nRole: {cardinal['role']}\nCountry: {cardinal['country']}\nOrder: {cardinal['order']}\n\nPolitical Analysis: {explanation}",
            political_leaning=political_leaning,
            data_dir=data_dir
        )
        
        processed_cardinals.append(cardinal_data)
        
        # Add delay to avoid overwhelming APIs
        time.sleep(2)
    
    # Save all cardinal data
    save_cardinals_data(processed_cardinals, data_dir)
    print(f"\nProcessed {len(processed_cardinals)} cardinals. Data saved in {data_dir}")
    
    # Get all political leanings
    leanings = [float(c['political_leaning']) for c in processed_cardinals]
    
    # Save political leaning summary to file
    save_political_summary("../", leanings)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Scrape and analyze cardinal data')
    parser.add_argument('--local', action='store_true', help='Use local LLM endpoint (default: use OpenAI)')
    parser.add_argument('--url', type=str, default='http://127.0.0.1:1234', help='Local LLM endpoint URL')
    parser.add_argument('--temperature', type=float, default=0.3, help='Temperature for LLM sampling')
    args = parser.parse_args()
    
    # Configure LLM based on arguments
    llm_config = LLMConfig(
        provider="local" if args.local else "openai",
        local_url=args.url,
        temperature=args.temperature
    )
    
    # Process cardinals with configured LLM
    process_cardinals(llm_config) 