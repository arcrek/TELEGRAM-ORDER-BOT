"""
Tests for state management.
Following TDD: Write tests first, then implement state management.
"""
from src.bot.states.state_manager import StateManager, UserState


class TestStateManager:
    """Test StateManager class."""

    def test_create_state_manager(self):
        """Test creating a state manager instance."""
        manager = StateManager()
        assert manager is not None

    def test_set_user_state(self):
        """Test setting user state."""
        manager = StateManager()
        user_id = 123456789
        
        state = UserState(
            current_page=1,
            selected_product_id=None,
            selected_variation_id=None,
            quantity=1,
            pending_order_id=None,
        )
        manager.set_user_state(user_id, state)
        
        retrieved = manager.get_user_state(user_id)
        assert retrieved is not None
        assert retrieved.current_page == 1
        assert retrieved.quantity == 1

    def test_get_user_state_nonexistent(self):
        """Test getting state for non-existent user."""
        manager = StateManager()
        user_id = 999999999
        
        state = manager.get_user_state(user_id)
        assert state is None

    def test_update_user_state(self):
        """Test updating user state."""
        manager = StateManager()
        user_id = 123456789
        
        # Set initial state
        initial_state = UserState(
            current_page=1,
            selected_product_id=None,
            selected_variation_id=None,
            quantity=1,
            pending_order_id=None,
        )
        manager.set_user_state(user_id, initial_state)
        
        # Update state
        manager.update_user_state(user_id, selected_product_id="prod_1", current_page=2)
        
        updated = manager.get_user_state(user_id)
        assert updated.selected_product_id == "prod_1"
        assert updated.current_page == 2
        assert updated.quantity == 1  # Should preserve other fields

    def test_clear_user_state(self):
        """Test clearing user state."""
        manager = StateManager()
        user_id = 123456789
        
        state = UserState(
            current_page=1,
            selected_product_id="prod_1",
            selected_variation_id=None,
            quantity=1,
            pending_order_id=None,
        )
        manager.set_user_state(user_id, state)
        
        manager.clear_user_state(user_id)
        
        cleared = manager.get_user_state(user_id)
        assert cleared is None

    def test_state_structure(self):
        """Test that state has all required fields."""
        state = UserState(
            current_page=1,
            selected_product_id="prod_1",
            selected_variation_id="var_1",
            quantity=5,
            pending_order_id="order_123",
        )
        
        assert state.current_page == 1
        assert state.selected_product_id == "prod_1"
        assert state.selected_variation_id == "var_1"
        assert state.quantity == 5
        assert state.pending_order_id == "order_123"

