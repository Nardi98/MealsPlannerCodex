"""Utility functions for Streamlit UI components."""

from __future__ import annotations

from typing import List

import streamlit as st


def ingredient_selector(
    container: "st.delta_generator.DeltaGenerator",
    label: str,
    options: List[str],
    *,
    key: str,
    default: str = "",
) -> str:
    """Render an ingredient input with dropdown suggestions.

    This widget mimics a basic autocomplete dropdown. Users can type to
    filter existing ingredient names and either select a suggestion or
    keep their custom entry to add a new ingredient.

    Parameters
    ----------
    container:
        Streamlit container (e.g. a column) where components are rendered.
    label:
        Label for the text input.
    options:
        List of known ingredient names for suggestions.
    key:
        Session state key for the text input.
    default:
        Optional default value for the input.

    Returns
    -------
    str
        The selected or typed ingredient name.
    """

    st.session_state.setdefault(key, default)
    current = st.session_state[key]

    # Filter available options based on current text
    filtered = [
        opt
        for opt in options
        if current and current.lower() in opt.lower() and opt != current
    ]

    select_key = f"{key}_select"
    suggestion_placeholder = container.empty()

    if filtered:
        selected = suggestion_placeholder.selectbox(
            "Suggestions",
            filtered,
            key=select_key,
            label_visibility="collapsed",
        )
        if selected != current:
            st.session_state[key] = selected
            current = selected
    else:
        suggestion_placeholder.empty()
        st.session_state.pop(select_key, None)

    # Render the main text input where users can type a name
    return container.text_input(label, key=key)

