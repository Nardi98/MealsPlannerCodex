"""Import and export data page."""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from mealplanner import crud
from mealplanner.db import SessionLocal, init_db
from mealplanner.models import Recipe


def main() -> None:
    """Render the import/export utilities."""
    st.header("Import / Export")
    init_db()

    if st.button("Export Data"):
        data = crud.export_data()
        st.download_button(
            "Download Export",
            data=data,
            file_name="mealplanner_data.json",
            mime="application/json",
        )
        st.code(data, language="json")

    def _do_import(file, mode: str) -> None:
        file.seek(0)
        try:
            crud.import_data(file, mode=mode)
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

    mode = st.radio("Import mode", ["overwrite", "merge"], index=0)
    uploaded = st.file_uploader("Import Data")
    if uploaded is not None and st.button("Import"):
        if mode == "overwrite":
            st.session_state["confirm_overwrite"] = True
        else:
            _do_import(uploaded, mode)

    if st.session_state.get("confirm_overwrite") and uploaded is not None:
        st.warning("This will delete the existing database. Are you sure?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete data"):
                _do_import(uploaded, "overwrite")
                st.session_state["confirm_overwrite"] = False
        with col2:
            if st.button("Cancel"):
                st.session_state["confirm_overwrite"] = False


if __name__ == "__main__":
    main()

