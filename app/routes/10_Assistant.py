import os
import json
from datetime import datetime, timezone
import litellm
import pandas as pd
import streamlit as st
from psycopg.rows import dict_row

# Import application reports and db configuration
import reports
from db import DATABASE_URL, pool

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Kandypack Logistics AI Assistant",
    page_icon="🤖",
    layout="wide",
)

MODEL_NAME = os.getenv("MODEL_NAME") or st.secrets.get("MODEL_NAME", "gemini/gemini-3.5-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if API_KEY:
    os.environ["GEMINI_API_KEY"] = API_KEY

@st.cache_data(ttl=3600)
def generate_schema_reference() -> str:
    """
    Dynamically introspects public tables, views, columns, and foreign keys
    using PostgreSQL information_schema and catalog views.
    """
    tables_query = """
        SELECT 
            c.table_name,
            c.column_name,
            c.data_type,
            c.udt_name,
            c.is_nullable
        FROM information_schema.columns c
        JOIN information_schema.tables t 
          ON c.table_name = t.table_name AND c.table_schema = t.table_schema
        WHERE c.table_schema = 'public' 
          AND t.table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY c.table_name, c.ordinal_position;
    """

    fk_query = """
        SELECT
            kcu.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public';
    """

    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(tables_query)
                columns_meta = cur.fetchall()

                cur.execute(fk_query)
                fks = cur.fetchall()

        fk_map = {
            (fk["source_table"], fk["source_column"]): f" -> {fk['target_table']}.{fk['target_column']}"
            for fk in fks
        }

        tables: dict[str, list[str]] = {}
        for row in columns_meta:
            tbl = row["table_name"]
            col = row["column_name"]
            dtype = row["udt_name"] if row["data_type"] == "USER-DEFINED" else row["data_type"]
            fk_target = fk_map.get((tbl, col), "")
            tables.setdefault(tbl, []).append(f"{col} {dtype}{fk_target}")

        lines = ["### Database Schema:"]
        for tbl, cols in tables.items():
            lines.append(f"- **{tbl}**: ({', '.join(cols)})")

        return "\n".join(lines)
    except Exception as exc:
        return f"### Schema Error: Could not read schema: {exc}"

def execute_select_query(query: str, params: dict | list | None = None) -> dict:
    """
    Executes an arbitrary SQL query enforcing read-only behavior at the
    database driver and transaction level.
    """
    st.caption("Executing read-only SQL query...")
    st.code(query, language="sql")
    try:
        # Enforce read-only mode directly on the driver connection
        with pool.connection() as conn:
            conn.read_only = True  # Native psycopg driver read-only enforcement
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '15s';")
                cur.execute(query, params)
                rows = cur.fetchall()
                if not rows:
                    return {"row_count": 0, "data": [], "truncated": False}
                return {
                    "row_count": len(rows),
                    "data": list(map(lambda row: row._asdict(), rows[:50])),  # Protect context window
                    "truncated": len(rows) > 50,
                }
    except Exception as exc:
        return {"error": f"Database Execution Error: {str(exc)}"}

def tool_quarterly_sales_report(year: int | None = None, quarter: int | None = None) -> dict:
    df = reports.get_quarterly_sales_report(year, quarter)
    return {"row_count": len(df), "data": df.head(50).to_dict(orient="records")}

def tool_most_ordered_items_report(year: int, quarter: int, limit: int = 10) -> dict:
    df = reports.get_most_ordered_items_report(year, quarter, limit)
    return {"row_count": len(df), "data": df.to_dict(orient="records")}

def tool_city_route_sales_report(start_date: str | None = None, end_date: str | None = None) -> dict:
    df = reports.get_city_route_sales_report(start_date, end_date)
    return {"row_count": len(df), "data": df.head(50).to_dict(orient="records")}

def tool_employee_working_hours_report(start_date: str, end_date: str) -> dict:
    df = reports.get_employee_working_hours_report(start_date, end_date)
    return {"row_count": len(df), "data": df.head(50).to_dict(orient="records")}

def tool_monthly_truck_usage_report(year: int, month: int) -> dict:
    df = reports.get_monthly_truck_usage_report(year, month)
    return {"row_count": len(df), "data": df.to_dict(orient="records")}

def tool_customer_order_history_report(customer_id: int | None = None) -> dict:
    df = reports.get_customer_order_history_report(customer_id)
    return {"row_count": len(df), "data": df.head(50).to_dict(orient="records")}

# Tool Registry
TOOL_RUNNERS = {
    "execute_select_query": lambda args: execute_select_query(args.get("query"), args.get("params")),
    "get_quarterly_sales_report": lambda args: tool_quarterly_sales_report(args.get("year"), args.get("quarter")),
    "get_most_ordered_items_report": lambda args: tool_most_ordered_items_report(args["year"], args["quarter"], args.get("limit", 10)),
    "get_city_route_sales_report": lambda args: tool_city_route_sales_report(args.get("start_date"), args.get("end_date")),
    "get_employee_working_hours_report": lambda args: tool_employee_working_hours_report(args["start_date"], args["end_date"]),
    "get_monthly_truck_usage_report": lambda args: tool_monthly_truck_usage_report(args["year"], args["month"]),
    "get_customer_order_history_report": lambda args: tool_customer_order_history_report(args.get("customer_id")),
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_select_query",
            "description": "Execute arbitrary read-only SQL queries on the Kandypack database. Used for custom analysis, aggregations, or queries not covered by standard reports.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The SQL SELECT or WITH query to run."},
                    "params": {"type": "object", "description": "Named query parameters as key-value pairs."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_quarterly_sales_report",
            "description": "Report 1: Retrieves quarterly total sales revenue and volume across the network.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Filter by year (e.g., 2024)."},
                    "quarter": {"type": "integer", "description": "Filter by quarter (1-4)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_most_ordered_items_report",
            "description": "Report 2: Returns the top products ordered within a quarter, ranked by quantity and revenue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Order year."},
                    "quarter": {"type": "integer", "description": "Order quarter (1-4)."},
                    "limit": {"type": "integer", "description": "Maximum number of items to return (default 10)."},
                },
                "required": ["year", "quarter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_city_route_sales_report",
            "description": "Report 3: Generates sales and order distributions aggregated by destination city and delivery route.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date filter in 'YYYY-MM-DD' format."},
                    "end_date": {"type": "string", "description": "End date filter in 'YYYY-MM-DD' format."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_working_hours_report",
            "description": "Report 4: Driver and assistant working hours report with threshold compliance (40h driver, 60h assistant limits).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Period start date in 'YYYY-MM-DD' format."},
                    "end_date": {"type": "string", "description": "Period end date in 'YYYY-MM-DD' format."},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_truck_usage_report",
            "description": "Report 5: Monthly truck metrics, trip counts, total operating hours, and items delivered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Calendar year."},
                    "month": {"type": "integer", "description": "Calendar month (1-12)."},
                },
                "required": ["year", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_order_history_report",
            "description": "Report 6: Traces customer orders with item statuses, rail schedules, and truck delivery assignments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "integer", "description": "Customer ID to filter, or null for all orders."},
                },
            },
        },
    },
]

def build_system_prompt() -> str:
    schema = generate_schema_reference()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""You are the senior logistics operations assistant for Kandypack FMCG (Kandy, Sri Lanka).
Current Time: {now_utc}.

Logistics Network Overview:
- Bulk freight moves from Kandy to regional station stores (Colombo, Negombo, Galle, Matara, Jaffna, Trincomalee) via Sri Lanka Railways.
- Last-mile deliveries are completed by trucks dispatched on defined routes.
- Roster restrictions: Drivers max 40 hrs/week with no back-to-back schedules; Assistants max 60 hrs/week with at most 2 consecutive routes.

{schema}

Instructions:
1. Always prefer using dedicated report functions (`get_*_report`) when answering standard report questions.
2. Use `execute_select_query` when the request requires custom aggregation, ad-hoc lookups, or joins not covered by the 6 standard reports.
3. Keep queries optimized and use proper parameter substitutions.
4. Provide structured, concise responses with Markdown tables for tabular figures.
"""

st.title("🤖 Kandypack Operations & Analytics Assistant")
st.caption("AI-powered assistant for logistics tracking, pre-built reports, and custom SQL analytics.")

# Sidebar Presets
with st.sidebar:
    st.header("Preset Inquiries")
    presets = [
        "Show quarterly sales breakdown for 2026",
        "Top 5 most ordered products in Q3 2026",
        "City and route sales distribution",
        "Driver & assistant hours between 2026-09-01 and 2026-09-30",
        "Truck usage report for June 2026",
        "Order history for customer #1",
        "Custom SQL: Train capacity utilization per destination",
    ]
    for p in presets:
        if st.button(p, use_container_width=True):
            st.session_state["preset_prompt"] = p
            st.rerun()

    if st.button("Clear Chat", type="secondary", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    if msg["role"] in ("user", "assistant") and msg.get("content"):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

user_input = st.session_state.pop("preset_prompt", None) or st.chat_input("Ask a logistics or reporting question...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    max_turns = 5
    turn = 0

    with st.chat_message("assistant"):
        response_box = st.empty()

        while turn < max_turns:
            turn += 1
            messages = [{"role": "system", "content": build_system_prompt()}] + st.session_state.chat_history

            with st.spinner("Processing request..."):
                try:
                    resp = litellm.completion(
                        model=MODEL_NAME,
                        messages=messages,
                        tools=TOOLS,
                        tool_choice="auto",
                    )
                    choice = resp.choices[0].message
                except Exception as err:
                    st.error(f"Inference error: {err}")
                    st.stop()

            # Handle Tool Calls
            if choice.tool_calls:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": choice.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in choice.tool_calls
                    ],
                })

                for tc in choice.tool_calls:
                    fn_name = tc.function.name
                    raw_args = tc.function.arguments
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})

                    with st.status(f"Running `{fn_name}`...", expanded=False) as status:
                        if fn_name in TOOL_RUNNERS:
                            result = TOOL_RUNNERS[fn_name](args)
                            status.update(label=f"`{fn_name}` finished", state="complete")
                            if "data" in result and result["data"]:
                                st.dataframe(result["data"])
                            else:
                                st.json(result)
                        else:
                            result = {"error": f"Tool '{fn_name}' not recognized."}
                            status.update(label=f"Failed `{fn_name}`", state="error")

                    st.session_state.chat_history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": json.dumps(result, default=str),
                    })
                continue

            # Assistant response completed
            final_text = choice.content or "No response returned."
            response_box.markdown(final_text)
            st.session_state.chat_history.append({"role": "assistant", "content": final_text})
            break
