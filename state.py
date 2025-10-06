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
    
    # New fields for fire NOC and land type
    fire_noc_required: Optional[bool] = None
    land_type_industrial: Optional[bool] = None
    
    # Search state
    search_results: Optional[str] = None
    current_page: int = 1
    requirements_confirmed: bool = False
    
    # Flow control - Enhanced for 3-state workflow
    workflow_stage: str = "area_and_size"  # area_and_size, land_type_preference, specifics
    next_action: str = "gather_requirements"
    conversation_complete: bool = False
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
    
    def get_missing_requirements(self) -> List[str]:
        """Identify which requirements are still missing based on current workflow stage."""
        missing = []
        
        if self.workflow_stage == "area_and_size":
            if not self.location_query:
                missing.append("location")
            if not self.size_min and not self.size_max:
                missing.append("size requirements")
        elif self.workflow_stage == "land_type_preference":
            if self.land_type_industrial is None:
                missing.append("land type preference")
        elif self.workflow_stage == "specifics":
            # In specifics stage, nothing is mandatory but we gather optional items
            pass
            
        return missing
    
    def is_ready_for_next_stage(self) -> bool:
        """Check if we can move to the next workflow stage."""
        if self.workflow_stage == "area_and_size":
            return bool(self.location_query and (self.size_min or self.size_max))
        elif self.workflow_stage == "land_type_preference":
            return self.land_type_industrial is not None
        elif self.workflow_stage == "specifics":
            return True  # Always ready to proceed from specifics
        return False
    
    def advance_workflow_stage(self):
        """Move to the next workflow stage."""
        if self.workflow_stage == "area_and_size":
            self.workflow_stage = "land_type_preference"
        elif self.workflow_stage == "land_type_preference":
            self.workflow_stage = "specifics"
        elif self.workflow_stage == "specifics":
            # Ready for search confirmation
            pass
    
    def is_ready_for_search(self) -> bool:
        """Check if we have minimum requirements for search."""
        return (self.workflow_stage == "specifics" and 
                bool(self.location_query and (self.size_min or self.size_max)) and
                self.land_type_industrial is not None)