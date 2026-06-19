"""Export-specific UserState fields."""
from src.bot.states.state_manager import StateManager, UserState


def test_userstate_export_defaults():
    st = UserState()
    assert st.export_products == []
    assert st.export_product_id is None
    assert st.export_variations == []
    assert st.export_selected_variation_ids == set()


def test_userstate_export_sets_are_independent():
    a, b = UserState(), UserState()
    a.export_selected_variation_ids.add("v1")
    assert b.export_selected_variation_ids == set()   # no shared mutable default


def test_set_and_get_roundtrip():
    mgr = StateManager()
    st = UserState()
    st.export_product_id = "p1"
    st.export_selected_variation_ids = {"v1", "v2"}
    mgr.set_user_state(42, st)
    got = mgr.get_user_state(42)
    assert got.export_product_id == "p1"
    assert got.export_selected_variation_ids == {"v1", "v2"}
