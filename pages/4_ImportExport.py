"""Import and export data page."""

from __future__ import annotations

import streamlit as st

from mealplanner import crud


def main() -> None:
    """Render the import/export utilities."""
    st.header("Import / Export")

    if st.button("Export Data"):
        data = crud.export_data()
        st.write(data)

    uploaded = st.file_uploader("Import Data")
    if uploaded is not None:
        crud.import_data(uploaded)
        st.success("Data imported")


if __name__ == "__main__":
    main()