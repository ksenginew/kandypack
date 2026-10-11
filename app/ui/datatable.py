import math
from typing import Callable, Optional, Tuple, Union
import pandas as pd
import streamlit as st
from streamlit import session_state

def render_datatable(
    data: Callable[[int, int], pd.DataFrame],
    total_count: int,
    key: str = "datatable",
    *args,
    **kwargs,
) -> list[dict]:
    """Renders a paginated table using a data function that accepts (limit, offset).

    Args:
        data: Callable accepting (limit, offset). Returns a pd.DataFrame.
        total_count: Total records available.
        page_size: Number of rows per page (the `limit`).
        key: Unique key prefix for Streamlit widgets.
        *args, **kwargs: Passed directly to `st.dataframe`.

    Returns:
        pd.DataFrame: Selected row(s) from the current page.
    """
    c1, c2 = st.columns([10, 2])
    with c2:
        limit = st.selectbox(
            "Rows per page",
            options=[5, 10, 20, 50, 100],
            key=f"{key}_page_size",
        )
        total_pages = max(1, math.ceil(total_count / limit))
    with c1:
        st.html("<small>&nbsp</small>")
        current_page = st.pagination(total_pages, key=f"{key}_pagination")

    offset = (current_page - 1) * limit
    result = data(limit, offset)

    kwargs.setdefault("use_container_width", True)
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("on_select", "rerun")
    kwargs.setdefault("selection_mode", "single-row")

    event = st.dataframe(result, *args, key=key, **kwargs)

    selected_indices = getattr(event.selection, "rows", [])
    if selected_indices:
        try:
            selected_data = result.iloc[selected_indices]
            st.session_state[f"{key}_selected"] = selected_data
            return selected_data.to_dict(orient="records")
        except IndexError:
            pass
    else:
        st.session_state[f"{key}_selected"] = None
        return None
