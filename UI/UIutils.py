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

    # Main text input where users can type a name
    input_value = container.text_input(label, value=default, key=key)

    # Filter available options based on user input
    filtered = [
        opt
        for opt in options
        if input_value and input_value.lower() in opt.lower() and opt != input_value
    ]

    # Placeholder for the dropdown suggestions
    suggestion_placeholder = container.empty()

    if filtered:
        # Display a selectbox with the filtered suggestions
        suggestion = suggestion_placeholder.selectbox(
            "Suggestions",
            filtered,
            key=f"{key}_select",
            label_visibility="collapsed",
        )
        if suggestion:
            # Update the text input with the chosen suggestion
            st.session_state[key] = suggestion
            input_value = suggestion
    else:
        # Clear the placeholder when there are no suggestions
        suggestion_placeholder.empty()
        # Remove stale suggestion state if present
        st.session_state.pop(f"{key}_select", None)

    return input_value

