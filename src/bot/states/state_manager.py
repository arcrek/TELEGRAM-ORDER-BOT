"""
State management for user sessions.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserState:
    """User session state."""
    
    current_page: int = 1
    selected_product_id: Optional[str] = None
    selected_variation_id: Optional[str] = None
    quantity: int = 1
    pending_order_id: Optional[str] = None
    payment_message_id: Optional[int] = None  # Telegram message ID of QR code payment message


class StateManager:
    """Manages user session states (in-memory storage)."""
    
    def __init__(self):
        """Initialize state manager."""
        self._states: dict[int, UserState] = {}
    
    def get_user_state(self, user_id: int) -> Optional[UserState]:
        """
        Get user state.
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            UserState if exists, None otherwise
        """
        return self._states.get(user_id)
    
    def set_user_state(self, user_id: int, state: UserState) -> None:
        """
        Set user state.
        
        Args:
            user_id: Telegram user ID
            state: UserState object
        """
        self._states[user_id] = state
    
    def update_user_state(
        self,
        user_id: int,
        current_page: Optional[int] = None,
        selected_product_id: Optional[str] = None,
        selected_variation_id: Optional[str] = None,
        quantity: Optional[int] = None,
        pending_order_id: Optional[str] = None,
        payment_message_id: Optional[int] = None,
    ) -> None:
        """
        Update user state with new values.
        
        Args:
            user_id: Telegram user ID
            current_page: Current page number
            selected_product_id: Selected product ID
            selected_variation_id: Selected variation ID
            quantity: Order quantity
            pending_order_id: Pending order ID
            payment_message_id: Telegram message ID of QR code payment message
        """
        state = self.get_user_state(user_id)
        if state is None:
            state = UserState()
        
        if current_page is not None:
            state.current_page = current_page
        if selected_product_id is not None:
            state.selected_product_id = selected_product_id
        if selected_variation_id is not None:
            state.selected_variation_id = selected_variation_id
        if quantity is not None:
            state.quantity = quantity
        if pending_order_id is not None:
            state.pending_order_id = pending_order_id
        if payment_message_id is not None:
            state.payment_message_id = payment_message_id
        
        self.set_user_state(user_id, state)
    
    def clear_user_state(self, user_id: int) -> None:
        """
        Clear user state.
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in self._states:
            del self._states[user_id]

