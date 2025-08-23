"""User interface helpers for the Meals Planner Codex application."""

from __future__ import annotations

from typing import Callable, List


__all__ = ["combobox_with_add"]


def combobox_with_add(
    key: str,
    placeholder: str,
    fetch_options: Callable[[str], List[str]],
    on_create: Callable[[str], None] | None = None,
    limit: int = 50,
) -> tuple[str | None, bool]:
    """Render a searchbox that lets users select or add items.

    Parameters
    ----------
    key:
        Unique key for the widget.
    placeholder:
        Placeholder text shown inside the input.
    fetch_options:
        Function returning a list of suggestions for a given query.
    on_create:
        Optional callback invoked when a new value is added.
    limit:
        Maximum number of suggestions to display. Defaults to 50.

    Returns
    -------
    tuple
        A tuple of the selected value (or ``None``) and a flag indicating
        whether a new value was created.
    """

    from streamlit_searchbox import st_searchbox

    ADD_PREFIX = "➕ Add ‘"
    ADD_SUFFIX = "’"

    def exact_exists(q: str, opts: List[str]) -> bool:
        qn = q.strip().lower()
        return any(o.strip().lower() == qn for o in opts)

    def make_add_label(q: str) -> str:
        return f"{ADD_PREFIX}{q.strip()}{ADD_SUFFIX}"

    def is_add_label(x: str) -> bool:
        return isinstance(x, str) and x.startswith(ADD_PREFIX) and x.endswith(ADD_SUFFIX)

    def extract_val(x: str) -> str:
        return x[len(ADD_PREFIX) : -len(ADD_SUFFIX)]

    def search_fn(user_input: str) -> List[str]:
        q = (user_input or "").strip()
        options = fetch_options(q)[:limit]
        if q and not exact_exists(q, options):
            options.append(make_add_label(q))
        return options

    picked = st_searchbox(
        search_function=search_fn,
        key=key,
        placeholder=placeholder,
        clear_on_submit=False,
    )

    created = False
    if isinstance(picked, str) and is_add_label(picked):
        val = extract_val(picked)
        if on_create:
            on_create(val)
        picked = val
        created = True

    return picked, created
