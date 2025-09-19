# state.py
from typing import Optional, List, Dict
from dataclasses import dataclass, field

@dataclass
class GraphState:
    """Central state object that tracks the conversation and user requirements."""
    
    # Conversation tracking
    messages: List[Dict[str, str]] = field(default_factory=list)
    
    # User requirements (slot-filling)
    location_query: Optional[str] = None
    parsed_cities: Optional[List[str]] = None
    parsed_state: Optional[str] = None
    size_min: Optional[int] = None
    size_max: Optional[int] = None
    budget_max: Optional[int] = None
    warehouse_type: Optional[str] = None
    compliances_query: Optional[str] = None
    min_docks: Optional[int] = None
    min_clear_height: Optional[int] = None
    availability: Optional[str] = None
    zone: Optional[str] = None
    is_broker: Optional[bool] = None
    
    # Search state
    search_results: Optional[str] = None
    current_page: int = 1
    requirements_confirmed: bool = False
    
    # Flow control
    next_action: str = "gather_requirements"
    conversation_complete: bool = False
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
    
    def get_missing_requirements(self) -> List[str]:
        """Identify which requirements are still missing."""
        missing = []
        if not self.location_query:
            missing.append("location")
        if not self.size_min and not self.size_max:
            missing.append("size requirements")
        return missing
    
    def is_ready_for_search(self) -> bool:
        """Check if we have minimum requirements for search."""
        return bool(self.location_query and (self.size_min or self.size_max or self.budget_max))