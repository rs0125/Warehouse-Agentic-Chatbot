import random

location_prompts = [
    "Where should we hunt for warehouses? (City, state, or region)",
    "Great! Which city or region are you eyeing for this warehouse?",
    "Got it 👍 — what’s the preferred location? (e.g., Bangalore or South India)",
]

size_prompts = [
    "Roughly how much space are you thinking? (like 50k sqft or a range)",
    "What size works for you? You can give a single number or a range.",
]

def choose_location_prompt():
    return random.choice(location_prompts)

def choose_size_prompt():
    return random.choice(size_prompts)
