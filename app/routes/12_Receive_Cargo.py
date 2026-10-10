import streamlit as st

def render(conn):
    st.title("📦 Receive Cargo at Store")
    st.write("Mark arriving rail cargo as received at the destination warehouse.")

    # Fetch train trips that have pending cargo
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT t.id, t.train_no, c.name as dest_city
            FROM train_trip t
            JOIN city c ON t.dest_city_id = c.id
            JOIN train_allocation ta ON t.id = ta.train_trip_id
            JOIN "order" o ON ta.order_id = o.id
            WHERE o.status IN ('Scheduled', 'In Rail Transit')
        """)
        pending_trips = cur.fetchall()

    if not pending_trips:
        st.success("All incoming rail cargo has already been received!")
        return

    # Format th options
    trip_options = {
        trip[0]: f"Train {trip[1]} arriving at {trip[2]} Store" 
        for trip in pending_trips
    }
    
    selected_trip_id = st.selectbox(
        "Select Arrived Train Trip", 
        options=list(trip_options.keys()), 
        format_func=lambda x: trip_options[x]
    )

    # Submission button
    if st.button("Confirm Cargo Receipt", type="primary"):
        try:
            with conn.cursor() as cur:
                # Call the PostgreSQL
                cur.execute("CALL receive_cargo_at_store(%s)", (selected_trip_id,))
                conn.commit()
            
            st.success(f"Cargo for {trip_options[selected_trip_id]} received successfully! Order statuses updated to 'At Store'.")
            st.balloons()
            
        except Exception as e:
            conn.rollback()
            st.error(f"A database error occurred: {e}")

