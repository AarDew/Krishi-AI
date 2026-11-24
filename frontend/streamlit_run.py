import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import pandas as pd
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ------------------- CONSTANTS ------------------- #
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", 
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal"
]

BACKEND_URL = "http://127.0.0.1:8000"
COMMODITY_FILE = os.path.join(os.path.dirname(__file__), '..', 'backend', 'commodity_price.csv')

# ------------------- SESSION STATE ------------------- #
DEFAULTS = {
    "logged_in": False,
    "user_role": None,
    "last_state": "",
    "crop_suggestions": [],
    "page": "main",
    "selected_crop": None,
    "analysis_data": None,
    "show_analysis": False,
    "current_analysis": None,
    "show_schedule": False,
    "schedule_data": None,
    "cached_recommendations": None,
    "last_schedule_request": None,
    "chat_messages": [],
    "show_chat": False,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ------------------- GLOBAL STYLE ------------------- #
st.set_page_config(page_title="KrishiAI", page_icon="🌱", layout="wide")
st.markdown("""
<style>
    .main-container { max-width: 1200px; margin: auto; padding: 20px; }
    .stButton button { width: 100%; border-radius: 12px; padding: 0.6em; margin: 0.3em 0; }
    .stTextInput input { border-radius: 8px; }
    .section-title { font-size: 22px; font-weight: bold; margin-top: 15px; }
    .card { background-color:#F0F2F6; border-radius:12px; padding:15px; margin-bottom:10px; }
</style>
""", unsafe_allow_html=True)

st.title("🌱 KrishiAI - Smart Farming Assistant")

# ------------------- HELPER FUNCTIONS ------------------- #
def toggle_analysis(crop_data, state, lat, lon):
    st.session_state.show_analysis = True
    st.session_state.current_analysis = {
        "crop": crop_data,
        "state": state,
        "latitude": lat,
        "longitude": lon
    }

def show_detailed_analysis(crop, state_name, latitude, longitude):
    st.title(f"📊 Detailed Analysis: {crop['crop']}")
    
    market_tab, weather_tab = st.tabs(["💹 Market Analysis", "🌤️ Weather Analysis"])
    
    with market_tab:
        st.subheader(f"💹 Market Analysis for {crop['crop']}")
        
        try:
            # Load local commodity price data
            df = pd.read_csv('commodity_price.csv')
            df['Arrival_Date'] = pd.to_datetime(df['Arrival_Date'], format='%d/%m/%Y')
            
            # Make crop name matching more flexible
            crop_search = crop['crop'].lower().strip()
            df['Commodity_Clean'] = df['Commodity'].str.lower().str.strip()
            
            # Try multiple variations of crop name
            variations = [
                crop_search,
                f"{crop_search}s",
                crop_search.replace(" ", ""),
                f"{crop_search}(raw)"
            ]
            
            crop_prices = df[df['Commodity_Clean'].str.contains('|'.join(variations), na=False, regex=True)]
            
            if not crop_prices.empty:
                # Calculate key metrics
                avg_price = crop_prices['Modal_x0020_Price'].mean()
                max_price = crop_prices['Max_x0020_Price'].max()
                min_price = crop_prices['Min_x0020_Price'].min()
                
                # Display price summary
                col1, col2, col3 = st.columns(3)
                col1.metric("Average Price", f"₹{avg_price:.2f}/ton")
                col2.metric("Maximum Price", f"₹{max_price:.2f}/ton")
                col3.metric("Minimum Price", f"₹{min_price:.2f}/ton")
                
                # Add time range selector 
                time_range = st.radio(
                    "Select Time Period",
                    ["Last Month", "Last 3 Months", "Last 6 Months"],
                    horizontal=True
                )
                
                # State-wise analysis
                st.subheader("Price Comparison by State")
                state_prices = crop_prices.groupby('State')['Modal_x0020_Price'].agg(['mean', 'min', 'max']).round(2)
                state_prices.columns = ['Average Price', 'Min Price', 'Max Price']
                
                fig_states = px.bar(state_prices,
                                y=state_prices.index,
                                x='Average Price',
                                title="Average Prices Across States",
                                labels={'y': 'State', 'x': 'Price (₹/kg)'})
                st.plotly_chart(fig_states, use_container_width=True)
                
                # Recent market prices table
                st.subheader("Recent Market Prices")
                recent_prices = crop_prices.sort_values('Arrival_Date', ascending=False).head(10)
                price_table = recent_prices[['State', 'District', 'Market', 
                                          'Min_x0020_Price', 'Max_x0020_Price',
                                          'Modal_x0020_Price', 'Arrival_Date']]
                price_table.columns = ['State', 'District', 'Market',
                                     'Min Price (₹/kg)', 'Max Price (₹/kg)',
                                     'Modal Price (₹/kg)', 'Date']
                st.dataframe(price_table)
                
            else:
                st.warning(f"No price data available for {crop['crop']}. Please check crop name or try a different crop.")
                
        except Exception as e:
            st.error(f"Error analyzing market data: {str(e)}")
            st.info("Please ensure the commodity price data file is available in the correct location.")

    with weather_tab:
        st.subheader("🌤️ Weather Analysis")
        
        # Add time range selector for weather
        weather_range = st.radio(
            "Select Forecast Range",
            ["7 Days", "3 Months", "6 Months"],
            horizontal=True,
            key="weather_range"
        )
        
        try:
            # Create weather metrics
            weather = crop['current_weather']
            col1, col2, col3 = st.columns(3)
            col1.metric("Temperature", f"{weather['temperature']:.1f}°C")
            col2.metric("Humidity", f"{weather['humidity']}%")
            col3.metric("Rainfall", f"{weather['rainfall']:.1f} mm")
            
            # Generate forecast data based on selected range
            days = 7 if weather_range == "7 Days" else 90 if weather_range == "3 Months" else 180
            dates = pd.date_range(start=datetime.now(), periods=days, freq='D')
            
            # Generate more realistic seasonal variations for longer forecasts
            base_temp = weather['temperature']
            base_humidity = weather['humidity']
            base_rainfall = weather['rainfall']
            
            forecast_temps = []
            forecast_humidity = []
            forecast_rain = []
            
            for i in range(days):
                # Add seasonal variation for longer forecasts
                seasonal_factor = np.sin(2 * np.pi * i / days)
                forecast_temps.append(base_temp + 5 * seasonal_factor + np.random.uniform(-2, 2))
                forecast_humidity.append(base_humidity + 10 * seasonal_factor + np.random.uniform(-5, 5))
                forecast_rain.append(max(0, base_rainfall + 2 * seasonal_factor + np.random.uniform(-1, 1)))
            
            fig_weather = go.Figure()
            
            fig_weather.add_trace(go.Scatter(x=dates, y=forecast_temps, 
                                           name='Temperature (°C)',
                                           line=dict(color='red')))
            fig_weather.add_trace(go.Scatter(x=dates, y=forecast_humidity, 
                                           name='Humidity (%)',
                                           line=dict(color='blue')))
            fig_weather.add_trace(go.Scatter(x=dates, y=forecast_rain, 
                                           name='Rainfall (mm)',
                                           line=dict(color='green')))
            
            fig_weather.update_layout(
                title=f'{weather_range} Weather Forecast',
                xaxis_title='Date',
                yaxis_title='Value',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_weather, use_container_width=True)

            # Add weather recommendations
            st.subheader("Weather-based Recommendations")
            if weather['temperature'] > 30:
                st.warning("⚠️ High temperature detected - Ensure adequate irrigation")
            if weather['humidity'] > 80:
                st.warning("⚠️ High humidity - Monitor for potential fungal diseases")
            if weather['rainfall'] > 5:
                st.info("☔ Good rainfall - Reduce irrigation")
                
        except Exception as e:
            st.error(f"Error analyzing weather data: {str(e)}")

def display_crop_card(crop_data, state_name, latitude, longitude):
    st.session_state.cached_recommendations = {
        "crop_data": crop_data, "state_name": state_name, "latitude": latitude, "longitude": longitude
    }
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🌾 {crop_data['crop']}")
            st.write(f"**Suitability:** {crop_data['probability']}")
            st.write(f"**Best Season:** {crop_data['season']}")
        with col2:
            price = crop_data['price']
            st.write("**Current Market Price:**")
            st.write(f"₹{price['min']} - ₹{price['max']} per kg")
            trend_emoji = "↗️" if price['trend'] == "rising" else "↘️" if price['trend'] == "falling" else "➡️"
            st.write(f"Price Trend: {trend_emoji} {price['trend'].title()}")
            weather = crop_data['current_weather']
            cols = st.columns(3)
            cols[0].metric("Temperature", f"{weather['temperature']:.1f}°C")
            cols[1].metric("Humidity", f"{weather['humidity']}%")
            cols[2].metric("Rainfall", f"{weather['rainfall']:.1f} mm")

        col1, col2 = st.columns([3, 1])
        with col2:
            st.button(f"📊 Analysis", key=f"analyze_{crop_data['crop']}", on_click=toggle_analysis,
                      args=(crop_data, state_name, latitude, longitude))
        schedule_key = f"{crop_data['crop']}_{state_name}"
        if st.button(f"🗓️ Get 3-Month Task Schedule", key=f"schedule_{crop_data['crop']}"):
            st.session_state.last_schedule_request = schedule_key
            with st.spinner("Generating crop schedule..."):
                schedule_params = {
                    "crop_name": crop_data['crop'],
                    "state": state_name,
                    "season": crop_data.get('season', 'current')
                }
                response = requests.post(f"{BACKEND_URL}/get_crop_schedule/", json=schedule_params)
                if response.status_code == 200:
                    st.session_state.schedule_data = {
                        "crop": crop_data['crop'],
                        "schedule": response.json().get("schedule"),
                        "request_key": schedule_key
                    }
                    st.session_state.show_schedule = True
                    st.rerun()
                else:
                    st.error("Could not generate crop schedule. Please try again.")

def show_schedule_page():
    schedule_info = st.session_state.schedule_data
    st.header(f"📅 3-Month Task Schedule for {schedule_info['crop']}")
    tasks = []
    schedule = schedule_info.get("schedule", {})
    if isinstance(schedule.get("tasks"), dict):
        tasks_dict = schedule["tasks"]
        tasks = [tasks_dict[k] for k in sorted(tasks_dict, key=lambda x: int(x))]
    else:
        tasks = schedule.get("tasks", [])

    week_map = {}
    for task in tasks:
        week = task.get("week_number", 0)
        if week not in week_map:
            week_map[week] = []
        week_map[week].append(task)

    if "task_status" not in st.session_state:
        st.session_state.task_status = {}

    total_tasks = 0
    completed_tasks = 0
    for week in sorted(week_map):
        st.subheader(f"Week {week}")
        for i, task in enumerate(week_map[week]):
            key = f"week{week}_{i}_{task['task_description'][:10]}"
            if key not in st.session_state.task_status:
                st.session_state.task_status[key] = False
            checked = st.checkbox(
                f"- {task['task_description']} ({task['category'].replace('_',' ').title()})",
                key=key, value=st.session_state.task_status[key]
            )
            st.session_state.task_status[key] = checked
            total_tasks += 1
            if checked:
                completed_tasks += 1

    st.progress(completed_tasks / total_tasks if total_tasks > 0 else 0)
    st.metric("Tasks Completed", f"{completed_tasks}/{total_tasks}")

    if st.button("← Back to Recommendations", key="back_to_recommendations"):
        st.session_state.show_schedule = False
        st.session_state.schedule_data = None
        st.rerun()

# ------------------- LOGIN / SIGNUP ------------------- #
if not st.session_state.logged_in:
    st.info("👋 Welcome! Please login or sign up to continue.")
    username = st.text_input("👤 Username")
    password = st.text_input("🔑 Password", type="password")
    role = st.radio("Login As", ["Farmer", "Buyer"], horizontal=True)
    c1, c2 = st.columns(2)

    if c1.button("🔒 Login"):
        resp = requests.post(f"{BACKEND_URL}/login/", json={"username": username, "password": password})
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.logged_in = True
            st.session_state.user_role = role
            st.session_state.username = username
            st.session_state.farmer_id = data.get("farmer_id")  # Store farmer_id
            st.success("✅ Logged in!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

    if c2.button("📝 Signup"):
        resp = requests.post(f"{BACKEND_URL}/signup/", json={"username": username, "password": password})
        st.success("🎉 Signup successful!") if resp.status_code == 200 else st.error("❌ Signup failed")

# ------------------- DASHBOARD ------------------- #
else:
    if st.session_state.user_role == "Farmer":
        st.header("👨‍🌾 Farmer Dashboard")
        tabs = st.tabs(["🌾 Farm Setup", "📊 Recommendations", "🔬 Disease Detection", "💹 Marketplace", "🤖 AI Assistant"])

        # ------------------- FARM SETUP ------------------- #
        with tabs[0]:
            st.subheader("🏡 Farm Details")
            farmer_name = st.text_input("👨‍🌾 Farmer Name")
            state_name = st.selectbox("📍 State", INDIAN_STATES)
            geolocator = Nominatim(user_agent="krishiai", timeout=10)
            try:
                location = geolocator.geocode(state_name)
            except GeocoderTimedOut:
                location = None

            if location:
                latitude, longitude = location.latitude, location.longitude
            else:
                latitude, longitude = 20.59, 78.96
                st.warning("⚠️ State not found. Showing India map.")

            m = folium.Map(location=[latitude, longitude], zoom_start=6)
            folium.Marker([latitude, longitude], popup=state_name).add_to(m)
            st_folium(m, width=700, height=400)

            if st.button("✅ Submit Farm Data"):
                if not farmer_name:
                    st.error("⚠️ Please enter your name!")
                else:
                    payload = {"name": farmer_name, "state": state_name, "latitude": latitude, "longitude": longitude}
                    resp = requests.post(f"{BACKEND_URL}/submit_farm_data/", json=payload)
                    st.success("Data submitted!") if resp.status_code == 200 else st.error("❌ Submission failed")

        # ------------------- CROP RECOMMENDATIONS ------------------- #
        with tabs[1]:
            st.subheader("🌱 Crop Recommendations")

            if st.session_state.show_schedule and st.session_state.schedule_data:
                show_schedule_page()
            elif st.session_state.show_analysis and st.session_state.current_analysis:
                if st.button("← Back to Recommendations", key="back_to_main"):
                    st.session_state.show_analysis = False
                    st.session_state.current_analysis = None
                    st.session_state.analysis_data = None
                else:
                    analysis = st.session_state.current_analysis
                    show_detailed_analysis(analysis["crop"], analysis["state"], analysis["latitude"], analysis["longitude"])
            else:
                if st.session_state.cached_recommendations and not st.button("🔍 Get New Recommendations"):
                    cached_data = st.session_state.cached_recommendations
                    display_crop_card(cached_data["crop_data"], cached_data["state_name"],
                                      cached_data["latitude"], cached_data["longitude"])
                    st.write("---")
                else:
                    selected_crop = st.selectbox("Select Crop (Optional)",
                                                 ["", "Rice", "Wheat", "Cotton", "Lentil", "Mango",
                                                  "Sugarcane", "Blackgram", "Maize", "Potato", "Tomato"])
                    if st.button("🔍 Get Crop Recommendations"):
                        try:
                            params = {
                                "state": state_name,
                                "latitude": latitude,
                                "longitude": longitude,
                                "temperature": 0,
                                "humidity": 0,
                                "rainfall": 0,
                                "preferred_crop": selected_crop
                            }
                            response = requests.post(f"{BACKEND_URL}/predict_crop/", json=params)
                            if response.status_code == 200:
                                crops = response.json().get("crop_suggestions", [])
                                if not crops:
                                    st.warning("No suitable crops found for your region.")
                                else:
                                    st.subheader("🌾 Recommended Crops for Your Region")
                                    for crop in crops:
                                        display_crop_card(crop, state_name, latitude, longitude)
                                    st.write("---")
                            else:
                                st.error("Could not get recommendations. Please try again.")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

        # ------------------- DISEASE DETECTION ------------------- #
        with tabs[2]:
            st.subheader("🔬 Upload Plant Image")
            file = st.file_uploader("Upload Image", type=["jpg","png","jpeg"])
            if file and st.button("Detect Disease"):
                files = {"file": file.getvalue()}
                resp = requests.post(f"{BACKEND_URL}/detect_disease/", files=files)
                if resp.status_code == 200:
                    result = resp.json()
                    st.success(f"🦠 {result['disease']} detected!")
                    st.write(f"Treatment: {result.get('treatment', 'N/A')}")
                else:
                    st.error("❌ Detection failed")

        # ------------------- MARKETPLACE ------------------- #
        with tabs[3]:
            st.subheader("💹 Marketplace")
            
            # Form to create new listing
            with st.form("new_listing"):
                st.write("Create New Listing")
                seller_name = st.text_input("Seller Name")  # Added this field
                crop_name = st.text_input("Crop Name")
                quantity = st.number_input("Quantity (kg)", min_value=0.1)
                price_per_kg = st.number_input("Price per kg (₹)", min_value=0.1)
                location = st.text_input("Location (City/Village)")
                state = st.selectbox("State", INDIAN_STATES)
                contact_number = st.text_input("Contact Number")
                
                if st.form_submit_button("Create Listing"):
                    if not all([seller_name, crop_name, quantity, price_per_kg, location, contact_number]):
                        st.error("Please fill all fields")
                    else:
                        try:
                            response = requests.post(
                                f"{BACKEND_URL}/marketplace/list/",
                                json={
                                    "seller_name": seller_name,
                                    "crop_name": crop_name,
                                    "quantity": quantity,
                                    "price_per_kg": price_per_kg,
                                    "location": location,
                                    "state": state,
                                    "contact_number": contact_number
                                }
                            )
                            if response.status_code == 200:
                                st.success("Listing created successfully!")
                                st.rerun()
                            else:
                                st.error(f"Failed to create listing: {response.text}")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

            # Show all listings
            st.subheader("Active Listings")
            try:
                response = requests.get(f"{BACKEND_URL}/marketplace/listings/")
                if response.status_code == 200:
                    listings = response.json().get("listings", [])
                    if not listings:
                        st.info("No active listings found")
                    else:
                        for listing in listings:
                            with st.container():
                                col1, col2 = st.columns([2,1])
                                with col1:
                                    st.write(f"**{listing['crop_name']}**")
                                    st.write(f"Seller: {listing['seller_name']}")
                                    st.write(f"Quantity: {listing['quantity']} kg")
                                    st.write(f"Price: ₹{listing['price_per_kg']}/kg")
                                with col2:
                                    st.write(f"Location: {listing['location']}")
                                    st.write(f"Contact: {listing['contact_number']}")
                else:
                    st.error("Failed to fetch listings")
            except Exception as e:
                st.error(f"Error fetching listings: {str(e)}")

        # ------------------- AI ASSISTANT ------------------- #
        with tabs[4]:
            st.subheader("🤖 AI Farming Assistant")
            
            # Custom CSS for chat messages
            st.markdown("""
                <style>
                .user-message {
                    background-color: #1e3a8a;
                    color: white;
                    padding: 15px;
                    border-radius: 15px;
                    margin: 5px 0;
                    text-align: right;
                }
                .assistant-message {
                    background-color: #374151;
                    color: white;
                    padding: 15px;
                    border-radius: 15px;
                    margin: 5px 0;
                    text-align: left;
                }
                .chat-container {
                    max-height: 400px;
                    overflow-y: auto;
                    padding: 10px;
                }
                </style>
            """, unsafe_allow_html=True)

            # Initialize chat messages if not exists
            if "chat_messages" not in st.session_state:
                st.session_state.chat_messages = []

            # Initialize session state for chat messages if not already present
            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Chat input area with improved UI
            with st.container():
                col1, col2 = st.columns([6,1])
                with col1:
                    user_input = st.text_input("Ask me anything about farming...", key="chat_input")
                with col2:
                    send_button = st.button("Send 📤", key="send_message")

                if (send_button or user_input) and user_input:
                    with st.spinner("🤔 Thinking..."):
                        try:
                            # Add system context for farming-specific responses
                            payload = {
                                "message": user_input,
                                "context": "You are an AI farming assistant. Provide detailed, practical advice about farming techniques, crop management, and agricultural best practices."
                            }  # Added closing brace
                            
                            resp = requests.post(f"{BACKEND_URL}/chat/", json=payload)
                            
                            if resp.status_code == 200:
                                reply = resp.json().get("reply", "")
                                # Store messages
                                st.session_state.chat_messages.append({"role": "user", "content": user_input})
                                st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                            else:
                                st.error("❌ Failed to get response from AI Assistant")
                        except Exception as e:
                            st.error(f"⚠️ Error: {str(e)}")

            def render_chat_messages():
                for message in st.session_state.messages:
                    if message["role"] == "user":
                        st.markdown(
                            f'<div class="user-message">{message["content"]}</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f'<div class="assistant-message">{message["content"]}</div>',
                            unsafe_allow_html=True
                        )

            # Display chat history
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            render_chat_messages()
            st.markdown('</div>', unsafe_allow_html=True)

            # Clear chat button
            if st.button("🗑️ Clear Chat", key="clear_chat"):
                st.session_state.chat_messages = []
                st.rerun()

    elif st.session_state.user_role == "Buyer":
        st.header("🛒 Buyer's Marketplace")
        
        # Add custom CSS for cards
        st.markdown("""
    <style>
    .marketplace-card {
        background-color: #1e1e1e;  /* dark card background */
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 6px rgba(255,255,255,0.1);
        border: 1px solid #333333;
        color: #ffffff;  /* default white text */
    }
    .price-tag {
        color: #00e676;  /* bright green for price */
        font-size: 20px;
        font-weight: bold;
    }
    .seller-info {
        color: #cccccc;
        font-size: 14px;
    }
    .filter-container {
        background-color: #2a2a2a;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: #ffffff;
    }
    .status-available {
        color: #00e676;
        font-weight: bold;
    }
    .crop-title {
        color: #64b5f6;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

        
        # Filters in a nice container
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.subheader("🔍 Search & Filter")
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_state = st.selectbox("📍 Select State", ["All States"] + INDIAN_STATES)
        with col2:
            filter_crop = st.text_input("🌾 Search by Crop")
        with col3:
            filter_location = st.text_input("🗺️ Search by Location")
            
        # Add sorting options
        sort_col1, sort_col2 = st.columns(2)
        with sort_col1:
            sort_by = st.selectbox("Sort by", ["Price: Low to High", "Price: High to Low", "Latest First"])
        with sort_col2:
            st.button("🔄 Refresh", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)
            
        try:
            # Fetch listings from backend
            params = {}
            if filter_state != "All States":
                params["state"] = filter_state
            if filter_crop:
                params["crop"] = filter_crop
            if filter_location:
                params["location"] = filter_location
                
            response = requests.get(f"{BACKEND_URL}/marketplace/listings/", params=params)
            
            if response.status_code == 200:
                listings = response.json().get("listings", [])
                
                # Sort listings based on selection
                if sort_by == "Price: Low to High":
                    listings = sorted(listings, key=lambda x: x['price_per_kg'])
                elif sort_by == "Price: High to Low":
                    listings = sorted(listings, key=lambda x: x['price_per_kg'], reverse=True)
                elif sort_by == "Latest First":
                    listings = sorted(listings, key=lambda x: x['created_at'], reverse=True)
                
                if not listings:
                    st.info("🔍 No listings found matching your criteria.")
                else:
                    st.subheader(f"📊 Found {len(listings)} Listings")
                    
                    # Display listings in a grid
                    cols = st.columns(2)
                    for idx, listing in enumerate(listings):
                        with cols[idx % 2]:
                            st.markdown(f"""
                                <div class="marketplace-card">
                                    <div class="crop-title">{listing['crop_name']}</div>
                                    <div class="price-tag">₹{listing['price_per_kg']}/kg</div>
                                    <p><strong>Quantity Available:</strong> {listing['quantity']} kg</p>
                                    <hr>
                                    <div class="seller-info">
                                        <p>📍 {listing['location']}, {listing['state']}</p>
                                        <p>👤 Seller: {listing['seller_name']}</p>
                                        <p>📞 Contact: {listing['contact_number']}</p>
                                    </div>
                                    <div class="status-available">✅ Available</div>
                                </div>
                            """, unsafe_allow_html=True)
                
            else:
                st.error("❌ Failed to fetch listings. Please try again.")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")
            
        # Help section with better styling
        with st.expander("💡 Need Help?"):
            st.markdown("""
            ### Contact Support
            - 📞 Helpline: +91 1234567890
            - 📧 Email: support@krishiai.com
            - ⏰ Available: Mon-Sat, 9 AM - 6 PM
            
            ### Quick Tips
            - Use filters to find specific crops
            - Contact sellers directly through provided numbers
            - Refresh the page to see new listings
            - Sort listings by price or date to find the best deals
            """)

    # ------------------- LOGOUT FUNCTIONALITY ------------------- #
    # Add this in the sidebar or header area of your app
    if st.session_state.logged_in:
        # Create a container for the logout button in the top right
        logout_container = st.container()
        with logout_container:
            col1, col2 = st.columns([6,1])
            with col2:
                if st.button("🚪 Logout", key="logout_button", type="secondary"):
                    # Clear all session state
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    # Reinitialize default session state
                    for key, value in DEFAULTS.items():
                        st.session_state[key] = value
                    st.rerun()
                    for key, value in DEFAULTS.items():
                        st.session_state[key] = value
                    st.rerun()

