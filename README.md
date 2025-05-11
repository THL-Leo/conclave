# Conclave Simulation

This project simulates a papal conclave using LLMs to simulate cardinal behavior. Each cardinal is simulated by an LLM that takes into account:
- The cardinal's biographical information
- Their voting history
- Results from previous rounds
- Political leanings (liberal vs conservative)

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Project Structure

- `cardinal.py`: Defines the Cardinal class and voting logic
- `conclave.py`: Main simulation orchestrator
- `data/`: Directory containing cardinal bios and voting history
- `utils.py`: Utility functions for data handling 