"""Streamlit UI helper utilities."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st


@contextmanager
def spinner(text: str) -> Iterator[None]:
    """Display a spinner with ``text`` while executing a block.

    Parameters
    ----------
    text:
        The message to show alongside the spinner.
    """

    with st.spinner(text):
        yield
