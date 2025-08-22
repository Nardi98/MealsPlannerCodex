"""Import and export data page."""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from mealplanner import crud
from mealplanner.db import SessionLocal
from mealplanner.models import Recipe


def main() -> None:
    """Render the import/export utilities."""
    st.header("Import / Export")

    if st.button("Export Data"):
        data = crud.export_data()
        st.download_button(
            "Download Export",
            data=data,
            file_name="mealplanner_data.json",
            mime="application/json",
        )
        st.code(data, language="json")

    mode = st.radio("Import mode", ["overwrite", "merge"], index=0)
    uploaded = st.file_uploader("Import Data")
    if uploaded is not None:
        try:
            crud.import_data(uploaded, mode=mode)
        except ValueError as exc:  # noqa: BLE001 - broad to show message
            st.error(f"Import failed: {exc}")
        else:
            st.success("Data imported")
            with SessionLocal() as session:
                titles = session.execute(select(Recipe.title)).scalars().all()
            if titles:
                st.write("Imported recipes:")
                for title in titles:
                    st.write(f"- {title}")
            else:
                st.write("No recipes found")


if __name__ == "__main__":
    main()

