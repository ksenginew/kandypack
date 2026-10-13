import streamlit as st
from db import fetch_all, execute_query

st.title("📦 Receive Cargo at Store")
st.write("Mark arriving rail cargo as received at the destination warehouse.")

# Fetch train schedules that have pending cargo (items still in transit)
pending_trips = fetch_all("""
    SELECT DISTINCT ts.id, s.store_name, ts.departure_timestamp
    FROM train_schedules ts
    JOIN stores s ON ts.destination_store_id = s.id
    JOIN train_allocations ta ON ts.id = ta.train_id
    JOIN order_items oi ON ta.order_item_id = oi.id
    WHERE oi.item_lifecycle_status IN ('SCHEDULED', 'IN_TRANSIT')
    ORDER BY ts.departure_timestamp ASC
""")

if not pending_trips:
    st.success("All incoming rail cargo has already been received!")
else:
    # Format the options
    trip_options = {
        trip[0]: f"Train #{trip[0]} → {trip[1]} (departed {trip[2].strftime('%Y-%m-%d %H:%M')})"
        for trip in pending_trips
    }

    selected_trip_id = st.selectbox(
        "Select Arrived Train Schedule",
        options=list(trip_options.keys()),
        format_func=lambda x: trip_options[x]
    )

    # Submission button
    if st.button("Confirm Cargo Receipt", type="primary"):
        try:
            execute_query("CALL receive_cargo_at_store(%s)", (selected_trip_id,))
            st.success(
                f"Cargo for {trip_options[selected_trip_id]} received successfully! "
                "Item statuses updated to 'At Store'."
            )
            st.balloons()
        except Exception as e:
            st.error(f"A database error occurred: {e}")