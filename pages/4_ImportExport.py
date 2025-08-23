"""Import and export data page."""

from __future__ import annotations

import io
import json

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

    def _do_import() -> None:
        raw = st.session_state.get("pending_upload")
        if raw is None:
            return
        mode: str = st.session_state.get("import_mode", "merge")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)

        if mode == "merge":
            with SessionLocal() as session:
                existing = set(session.execute(select(Recipe.title)).scalars())
            dup_titles = [r["title"] for r in data.get("recipes", []) if r["title"] in existing]

            if dup_titles:
                if not st.session_state.get("duplicate_actions_confirmed"):
                    st.info(
                        "Recipes with matching titles were found. Choose how to proceed:"
                    )
                    for title in dup_titles:
                        st.radio(
                            f"Recipe '{title}' exists already",
                            ["keep old", "keep new", "keep both"],
                            key=f"dup_action_{title}",
                        )
                    if not st.button("Continue Import"):
                        return
                    st.session_state["duplicate_actions_confirmed"] = True
                    st.session_state["duplicate_titles"] = dup_titles

                with SessionLocal() as session:
                    for rec in list(data.get("recipes", [])):
                        title = rec.get("title")
                        if title not in st.session_state.get("duplicate_titles", []):
                            continue
                        action = st.session_state.get(f"dup_action_{title}")
                        if action == "keep old":
                            data["recipes"].remove(rec)
                        elif action == "keep new":
                            existing_rec = session.execute(
                                select(Recipe).where(Recipe.title == title)
                            ).scalar_one_or_none()
                            if existing_rec is not None:
                                session.delete(existing_rec)
                    session.commit()
                for title in st.session_state.get("duplicate_titles", []):
                    st.session_state.pop(f"dup_action_{title}", None)
                st.session_state.pop("duplicate_titles", None)
                st.session_state.pop("duplicate_actions_confirmed", None)

        file_obj = io.StringIO(json.dumps(data))
        try:
            crud.import_data(file_obj, mode=mode)
        except ValueError as exc:  # noqa: BLE001 - broad to show message
            st.error(f"Import failed: {exc}")
        else:
            st.success("Data imported successfully. Redirecting to recipes...")
            st.markdown(
                """
                <meta http-equiv="refresh" content="1.5; url=/?page=1_Recipes">
                """,
                unsafe_allow_html=True,
            )
        finally:
            st.session_state.pop("pending_upload", None)
            st.session_state.pop("uploaded_file", None)
            st.session_state.pop("import_mode", None)

    mode = st.radio("Import mode", ["overwrite", "merge"], index=0)
    uploaded = st.file_uploader("Import Data")
    if uploaded is not None and st.button("Import"):
        st.session_state["uploaded_file"] = uploaded.getvalue()
        st.session_state["import_mode"] = mode
        if mode == "overwrite":
            st.session_state["confirm_overwrite"] = True
        else:
            st.session_state["pending_upload"] = st.session_state["uploaded_file"]

    if st.session_state.get("confirm_overwrite") and st.session_state.get("uploaded_file") is not None:
        st.warning("This will delete the existing database. Are you sure?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete data"):
                st.session_state["pending_upload"] = st.session_state["uploaded_file"]
                st.session_state["confirm_overwrite"] = False
        with col2:
            if st.button("Cancel"):
                st.session_state["confirm_overwrite"] = False
                st.session_state.pop("uploaded_file", None)

    if st.session_state.get("pending_upload") is not None and not st.session_state.get("confirm_overwrite", False):
        _do_import()


if __name__ == "__main__":
    main()

