from typing import Any, Dict, Optional
import streamlit as st


def render_input(
    field_name: str,
    field_spec: Dict[str, Any],
    is_required: bool = False,
    key_prefix: str = "",
) -> Any:
    """Renders a single flat Streamlit widget matching simple JSON Schema field types."""
    field_type = field_spec.get("type", "string")
    title = field_spec.get("title", field_name.replace("_", " ").title())
    description = field_spec.get("description", "")
    default = field_spec.get("default")
    enum_values = field_spec.get("enum")
    widget_key = f"{key_prefix}_{field_name}"

    label = f"{title} *" if is_required else title

    # 1. Enum options -> Selectbox
    if enum_values:
        default_idx = (
            enum_values.index(default) if default in enum_values else 0
        )
        return st.selectbox(
            label=label,
            options=enum_values,
            index=default_idx,
            help=description,
            key=widget_key,
        )

    # 2. Numeric handling -> number_input
    elif field_type in ("integer", "number"):
        is_int = field_type == "integer"
        min_val = field_spec.get("minimum")
        max_val = field_spec.get("maximum")
        step = 1 if is_int else field_spec.get("multipleOf", 0.01)

        # Cast bounds appropriately
        if min_val is not None:
            min_val = int(min_val) if is_int else float(min_val)
        if max_val is not None:
            max_val = int(max_val) if is_int else float(max_val)

        # Determine starting value
        if default is not None:
            val = int(default) if is_int else float(default)
        elif min_val is not None:
            val = min_val
        else:
            val = 0 if is_int else 0.0

        return st.number_input(
            label=label,
            min_value=min_val,
            max_value=max_val,
            value=val,
            step=step,
            help=description,
            key=widget_key,
        )

    # 4. Boolean handling -> checkbox
    elif field_type == "boolean":
        return st.checkbox(
            label=label,
            value=bool(default) if default is not None else False,
            help=description,
            key=widget_key,
        )


    # 5. String handling -> text_input, text_area, date_input, time_input
    else:
        schema_format = field_spec.get("format")

        if schema_format == "date":
            return st.date_input(
                label=label,
                value=default or "today",
                help=description,
                key=widget_key,
                min_value=field_spec.get("minimum"),
                max_value=field_spec.get("maximum"),
            )
        elif schema_format == "time":
            return st.time_input(
                label=label,
                value=default or "now",
                help=description,
                key=widget_key,
            )
        elif schema_format == "password" or field_spec.get("writeOnly", False):
            return st.text_input(
                label=label,
                value=default or "",
                type="password",
                help=description,
                key=widget_key,
                max_chars=field_spec.get("maxLength", None)
            )
        elif schema_format == "multiline" or field_spec.get("maxLength", 0) > 100:
            return st.text_area(
                label=label,
                value=default or "",
                help=description,
                key=widget_key,
                max_chars=field_spec.get("maxLength", None)
            )
        else:
            return st.text_input(
                label=label,
                value=default or "",
                help=description,
                key=widget_key,
                max_chars=field_spec.get("maxLength", None)
            )


def render_form(
    schema: Dict[str, Any],
    form_key: str = "simple_form",
    submit_label: str = "Submit",
    clear_on_submit: bool = False,
) -> Optional[Dict[str, Any]]:
    """Renders a flat Streamlit form based on a JSON Schema and validates required fields."""
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    with st.form(key=form_key, clear_on_submit=clear_on_submit):
        form_data = {}
        for name, spec in properties.items():
            if spec.get("readOnly", False):
                continue  # Skip read-only fields
            is_req = name in required_fields
            form_data[name] = render_input(
                field_name=name,
                field_spec=spec,
                is_required=is_req,
                key_prefix=form_key,
            )

        submitted = st.form_submit_button(submit_label)

        if submitted:
            missing = [
                properties[f].get("title", f)
                for f in required_fields
                if form_data.get(f) in (None, "")
            ]

            if missing:
                st.error(f"Please fill in required fields: {', '.join(missing)}")
                return None

            st.success("Form submitted successfully!")
            return form_data

    return None