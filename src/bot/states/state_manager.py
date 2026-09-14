"""
State management for user sessions.
"""
from dataclasses import dataclass, field
from typing import Self


@dataclass
class UserState:
    """User session state."""

    current_page: int = 1
    selected_product_id: str | None = None
    selected_variation_id: str | None = None
    quantity: int = 1
    pending_order_id: str | None = None
    payment_message_id: int | None = None  # Telegram message ID of QR code payment message
    payment_message_ids: list | None = None  # List of all payment-related message IDs to delete
    waiting_for_custom_quantity: bool = False  # Flag for custom quantity input mode
    custom_quantity_prompt_message_id: int | None = None  # Message ID of the prompt to delete
    order_message_id: int | None = None  # Message ID of the order confirmation message

    # Balance / topup flow state
    awaiting_topup_amount: bool = False  # True while waiting for custom amount text input
    pending_topup_order_id: str | None = None  # Currently-pending TopupOrder being paid
    pending_payment_order_id: str | None = None  # Product Order in payment-method-picker step
    topup_message_id: int | None = None  # Main topup flow message ID (for edit-in-place)
    topup_payment_message_ids: list = field(default_factory=list)  # QR/photo messages for topup
    balance_message_id: int | None = None  # Main balance view message ID

    # /export flow state
    export_products: list = field(default_factory=list)  # [{"id","name"}] shown
    export_product_id: str | None = None              # product chosen in step 1
    export_variations: list = field(default_factory=list)  # [{"id","name"}] of that product
    export_selected_variation_ids: set = field(default_factory=set)  # toggled variants
    export_target_user_id: int | None = None          # admin-proxy: target user's telegram_user_id

    # /set_emo flow state
    awaiting_emoji_input: bool = False
    pending_emoji_placeholder_id: int | None = None


class StateManager:
    """Manages user session states (in-memory storage singleton)."""

    _instance: "StateManager | None" = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._states = {}
        return cls._instance

    def __init__(self) -> None:
        """Initialize state manager (idempotent for singleton)."""
        if not hasattr(self, "_states"):
            self._states: dict[int, UserState] = {}
    
    def get_user_state(self, user_id: int) -> UserState | None:
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
        current_page: int | None = None,
        selected_product_id: str | None = None,
        selected_variation_id: str | None = None,
        quantity: int | None = None,
        pending_order_id: str | None = None,
        payment_message_id: int | None = None,
        payment_message_ids: list | None = None,
        waiting_for_custom_quantity: bool | None = None,
        custom_quantity_prompt_message_id: int | None = None,
        order_message_id: int | None = None,
        awaiting_topup_amount: bool | None = None,
        pending_topup_order_id: str | None = None,
        pending_payment_order_id: str | None = None,
        topup_message_id: int | None = None,
        topup_payment_message_ids: list | None = None,
        balance_message_id: int | None = None,
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
            payment_message_ids: List of all payment-related message IDs to delete
            waiting_for_custom_quantity: Flag for custom quantity input mode
            custom_quantity_prompt_message_id: Message ID of the prompt to delete
            order_message_id: Message ID of the order confirmation message
            awaiting_topup_amount: True while waiting for custom amount text input
            pending_topup_order_id: Currently-pending TopupOrder being paid
            pending_payment_order_id: Product Order in payment-method-picker step
            topup_message_id: Main topup flow message ID (for edit-in-place)
            topup_payment_message_ids: QR/photo messages for topup
            balance_message_id: Main balance view message ID
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
        if payment_message_ids is not None:
            state.payment_message_ids = payment_message_ids
        if waiting_for_custom_quantity is not None:
            state.waiting_for_custom_quantity = waiting_for_custom_quantity
        if custom_quantity_prompt_message_id is not None:
            state.custom_quantity_prompt_message_id = custom_quantity_prompt_message_id
        if order_message_id is not None:
            state.order_message_id = order_message_id
        if awaiting_topup_amount is not None:
            state.awaiting_topup_amount = awaiting_topup_amount
        if pending_topup_order_id is not None:
            state.pending_topup_order_id = pending_topup_order_id
        if pending_payment_order_id is not None:
            state.pending_payment_order_id = pending_payment_order_id
        if topup_message_id is not None:
            state.topup_message_id = topup_message_id
        if topup_payment_message_ids is not None:
            state.topup_payment_message_ids = topup_payment_message_ids
        if balance_message_id is not None:
            state.balance_message_id = balance_message_id

        self.set_user_state(user_id, state)
    
    def clear_user_state(self, user_id: int) -> None:
        """
        Clear user state.
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in self._states:
            del self._states[user_id]

    def clear_all(self) -> None:
        """Clear all user states (useful for resets and tests)."""
        self._states.clear()


# Shared singleton instance
shared_state_manager = StateManager()

