from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator  # Updated import
from sqlalchemy import create_engine, Column, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import bcrypt
import uuid
import requests
import os
import logging
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import aiohttp
from aiohttp import ClientTimeout
from google import genai
import asyncio
import uvicorn
from typing import Optional, List, Dict, Any  # Add type hints

PROJECT_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = PROJECT_DIR.parent
COMMODITY_DATA_PATH = PROJECT_DIR / "commodity_price.csv"
CROP_DATA_PATH = PROJECT_DIR / "crop_data.csv"
load_dotenv(REPOSITORY_DIR / ".env")
logger = logging.getLogger(__name__)
AGRICULTURE_PRICE_API_URL = os.getenv("AGRICULTURE_PRICE_API_URL")
AGRICULTURE_PRICE_API_KEY = os.getenv("AGRICULTURE_PRICE_API_KEY")

# Database setup
DATABASE_PATH = Path(
    os.getenv("KRISHIAI_DB_PATH", str(PROJECT_DIR / "krishiai.db"))
).expanduser().resolve()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# User model
class User(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)

# Farmer Data model - Updated schema
class Farmer(Base):
    __tablename__ = "farmers"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    state = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

# Commodity Price model
class CommodityPrice(Base):
    __tablename__ = "commodity_prices"
    id = Column(String, primary_key=True, index=True)
    state = Column(String, nullable=False)
    district = Column(String, nullable=False)
    market = Column(String, nullable=False)
    commodity = Column(String, nullable=False)
    variety = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    arrival_date = Column(String, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    modal_price = Column(Float, nullable=False)

# Marketplace model
class MarketListing(Base):
    __tablename__ = "market_listings"
    id = Column(String, primary_key=True, index=True)
    seller_name = Column(String, nullable=False)
    crop_name = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price_per_kg = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    state = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    status = Column(String, nullable=False, default="available")
    contact_number = Column(String, nullable=False)  # Added this field

def init_database():
    Base.metadata.create_all(bind=engine)


init_database()

# FastAPI app
app = FastAPI(title="KrishiAI API")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str
    
    @field_validator('username')  # Updated decorator
    def username_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Username cannot be empty')
        return v.strip()

class LoginResponse(BaseModel):
    message: str
    token: str
    farmer_id: Optional[str] = None

class FarmerCreate(BaseModel):
    name: str
    state: str
    latitude: float
    longitude: float

    @field_validator('latitude')  # Changed from @validator
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v

    @field_validator('longitude')  # Changed from @validator
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v

class CropPredictionRequest(BaseModel):
    state: str
    nitrogen: float = 0.0
    phosphorus: float = 0.0
    potassium: float = 0.0
    temperature: float = 25.0
    humidity: float = 50.0
    ph_value: float = 7.0
    rainfall: float = 100.0
    latitude: float
    longitude: float

    @field_validator('latitude')  # Changed from @validator
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v

    @field_validator('longitude')  # Changed from @validator
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v

    @field_validator('state')  # Changed from @validator
    def validate_state(cls, v):
        if not v.strip():
            raise ValueError('State cannot be empty')
        return v.strip()

    @field_validator('nitrogen', 'phosphorus', 'potassium', 'temperature', 'humidity', 'ph_value', 'rainfall')  # Changed from @validator
    def validate_non_negative(cls, v):
        if v < 0:
            raise ValueError('Value cannot be negative')
        return v

class CropPredictionResponse(BaseModel):
    crop_suggestions: list

class DetailedAnalysisRequest(BaseModel):
    crop_name: str
    state: str
    latitude: float
    longitude: float

class WeatherForecast(BaseModel):
    date: str
    temperature: float
    humidity: float
    rainfall: float

class MarketTrend(BaseModel):
    date: str
    price: float
    volume: float

class DetailedAnalysisResponse(BaseModel):
    weather_forecast: list[WeatherForecast]
    market_trends: list[MarketTrend]
    weather_graph: dict
    price_graph: dict

class CropScheduleRequest(BaseModel):
    crop_name: str
    state: str
    season: str

class ChatMessage(BaseModel):
    message: str

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Signup route
@app.post("/signup/", response_model=LoginResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    if not user.username or not user.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed_password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    new_user = User(username=user.username, password=hashed_password)
    db.add(new_user)
    db.commit()
    return {"message": "User registered successfully", "token": "dummy_token"}

# Login route
@app.post("/login/", response_model=LoginResponse)
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not bcrypt.checkpw(user.password.encode("utf-8"), db_user.password.encode("utf-8")):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # Get or create farmer record
    farmer = db.query(Farmer).filter(Farmer.name == user.username).first()
    if not farmer:
        farmer = Farmer(
            id=str(uuid.uuid4()),
            name=user.username,
            state="Unknown",  # Will be updated when farm details are submitted
            latitude=0,
            longitude=0
        )
        db.add(farmer)
        db.commit()
    
    return {
        "message": "Login successful", 
        "token": "dummy_token",
        "farmer_id": farmer.id
    }

# Save farmer data route
@app.post("/submit_farm_data/")
async def submit_farm_data(farmer: FarmerCreate, db: Session = Depends(get_db)):
    try:
        print(f"Received farmer data: {farmer.dict()}")  # Debug print
        
        farmer_id = str(uuid.uuid4())
        new_farmer = Farmer(
            id=farmer_id,
            name=farmer.name,
            state=farmer.state,
            latitude=farmer.latitude,
            longitude=farmer.longitude
        )
        db.add(new_farmer)
        db.commit()
        
        return {"message": "Farmer data saved successfully", "id": farmer_id}
    except Exception as e:
        print(f"Error saving farmer data: {str(e)}")  # Debug print
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save farmer data: {str(e)}")

# Fetch state-wise crop prices
def fetch_crop_prices(state):
    if not AGRICULTURE_PRICE_API_URL:
        raise RuntimeError("AGRICULTURE_PRICE_API_URL is not configured")

    headers = {}
    if AGRICULTURE_PRICE_API_KEY:
        headers["Authorization"] = f"Bearer {AGRICULTURE_PRICE_API_KEY}"

    response = requests.get(
        AGRICULTURE_PRICE_API_URL,
        params={"state": state},
        headers=headers,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()

# Load and prepare dataset
def prepare_model():
    if not CROP_DATA_PATH.is_file():
        logger.warning(
            "Crop dataset not found at %s; data-backed crop modeling is unavailable",
            CROP_DATA_PATH,
        )
        return None, None, None, None

    df = pd.read_csv(CROP_DATA_PATH)
    if df.empty:
        logger.warning("Crop dataset is empty at %s", CROP_DATA_PATH)
        return None, None, None, None

    df.columns = df.columns.str.strip()
    return None, None, None, df

model, state_encoder, crop_encoder, crop_data = prepare_model()

def get_current_season():
    # Define seasons based on months
    current_month = datetime.now().month
    if 3 <= current_month <= 5:
        return "Summer"
    elif 6 <= current_month <= 9:
        return "Monsoon"
    elif 10 <= current_month <= 11:
        return "Post-Monsoon"
    else:
        return "Winter"

def get_season_for_crop(crop_name):
    # Define season rules for different crops
    crop_seasons = {
        'Rice': 'Kharif',
        'Maize': 'Kharif',
        'ChickPea': 'Rabi',
        'KidneyBeans': 'Kharif',
        'PigeonPeas': 'Kharif',
        'MothBeans': 'Kharif',
        'MungBean': 'Kharif',
        'Blackgram': 'Kharif',
        'Lentil': 'Rabi',
        'Pomegranate': 'Perennial',
        'Banana': 'Perennial',
        'Mango': 'Perennial',
        'Grapes': 'Perennial',
        'Watermelon': 'Summer',
        'Muskmelon': 'Summer',
        'Apple': 'Perennial',
        'Orange': 'Perennial',
        'Papaya': 'Perennial',
        'Coconut': 'Perennial',
        'Cotton': 'Kharif',
        'Jute': 'Kharif',
        'Wheat': 'Rabi',
        'Sugarcane': 'Perennial',
        'Groundnut': 'Kharif',
        'Soybean': 'Kharif',
        'Tomato': 'All Season',
        'Potato': 'Rabi',
        'Onion': 'Rabi',
        'Garlic': 'Rabi',
        'Turmeric': 'Kharif'
    }
    return crop_seasons.get(crop_name, 'Unknown')

# Load environment variables
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

async def get_weather_data(lat: float, lon: float):
    try:
        if not OPENWEATHER_API_KEY:
            # Return dummy data if no API key
            return {
                "temperature": 25.0,
                "humidity": 65.0,
                "rainfall": 50.0
            }
            
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "temperature": data["main"]["temp"],
                        "humidity": data["main"]["humidity"],
                        "rainfall": data.get("rain", {}).get("1h", 0) * 24  # Convert to daily
                    }
                else:
                    print(f"Weather API error: {await response.text()}")
                    return None
    except Exception as e:
        print(f"Weather API error: {str(e)}")
        return None

async def get_weather_forecast(lat: float, lon: float, days: int = 180):  # Changed to 180 days
    try:
        if not OPENWEATHER_API_KEY:
            # Return dummy forecast for 6 months
            forecast = []
            base_temp = 25.0
            base_humidity = 65.0
            base_rainfall = 50.0
            for i in range(days):
                date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                # More realistic seasonal variations
                month = (datetime.now() + timedelta(days=i)).month
                # Seasonal temperature adjustments
                seasonal_temp = base_temp + 5 * np.sin(2 * np.pi * (i/365))  # Yearly cycle
                temp = seasonal_temp + np.random.normal(0, 2)
                
                # Seasonal humidity and rainfall
                if 6 <= month <= 9:  # Monsoon
                    humidity = base_humidity + 20 + np.random.normal(0, 5)
                    rainfall = max(0, base_rainfall * 2 + np.random.normal(0, 30))
                elif 10 <= month <= 11:  # Post-monsoon
                    humidity = base_humidity + 10 + np.random.normal(0, 5)
                    rainfall = max(0, base_rainfall + np.random.normal(0, 20))
                elif month <= 2:  # Winter
                    humidity = base_humidity - 10 + np.random.normal(0, 5)
                    rainfall = max(0, base_rainfall * 0.3 + np.random.normal(0, 10))
                else:  # Summer
                    humidity = base_humidity - 20 + np.random.normal(0, 5)
                    rainfall = max(0, base_rainfall * 0.1 + np.random.normal(0, 5))
                
                forecast.append(WeatherForecast(
                    date=date,
                    temperature=round(temp, 1),
                    humidity=round(humidity, 1),
                    rainfall=round(rainfall, 1)
                ))
            return forecast

        # For the actual API, we'll continue with 7-day forecast as OpenWeather free tier limitation
        timeout = ClientTimeout(total=10)
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    forecast = []
                    for item in data['list'][:days*8:8]:  # Get daily data
                        temp = item['main']['temp']
                        humidity = item['main']['humidity']
                        rainfall = item.get('rain', {}).get('3h', 0) * 8
                        
                        forecast.append(WeatherForecast(
                            date=datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d'),
                            temperature=round(temp, 1),
                            humidity=round(humidity, 1),
                            rainfall=round(rainfall, 1)
                        ))
                    return forecast
                else:
                    print(f"Weather forecast API error: {await response.text()}")
                    return None
    except Exception as e:
        print(f"Weather forecast API error: {str(e)}")
        return None

async def get_crop_price(crop_name: str):
    try:
        crop_prices = {
            "Rice": {"min": 18.5, "max": 22.0, "trend": "stable"},
            "Wheat": {"min": 20.0, "max": 24.0, "trend": "rising"},
            "Maize": {"min": 15.0, "max": 18.0, "trend": "falling"},
            "Cotton": {"min": 45.0, "max": 55.0, "trend": "stable"},
            "Sugarcane": {"min": 3.0, "max": 4.0, "trend": "stable"},
            "Potato": {"min": 12.0, "max": 15.0, "trend": "rising"},
            "Onion": {"min": 15.0, "max": 25.0, "trend": "volatile"},
            "Tomato": {"min": 20.0, "max": 35.0, "trend": "volatile"},
            "Groundnut": {"min": 40.0, "max": 50.0, "trend": "stable"},
            "Soybean": {"min": 35.0, "max": 42.0, "trend": "rising"},
            "ChickPea": {"min": 45.0, "max": 55.0, "trend": "stable"},
            "Turmeric": {"min": 65.0, "max": 85.0, "trend": "rising"},
            "Garlic": {"min": 40.0, "max": 60.0, "trend": "stable"}
        }
        return crop_prices.get(crop_name, {"min": 0, "max": 0, "trend": "unknown"})
    except Exception as e:
        print(f"Price API error: {str(e)}")
        return None

async def get_market_history(crop_name: str, days: int = 30):
    try:
        # Simulate historical data - replace with actual API call
        base_price = get_crop_price(crop_name)['min']
        history = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            # Simulate some price variation
            price = base_price * (1 + np.random.normal(0, 0.1))
            volume = np.random.randint(1000, 5000)
            history.append(MarketTrend(
                date=date,
                price=round(price, 2),
                volume=volume
            ))
        return history
    except Exception as e:
        print(f"Market history error: {str(e)}")
        return None

@app.post("/predict_crop/", response_model=CropPredictionResponse)
async def predict_crop(data: CropPredictionRequest):
    raise HTTPException(
        status_code=503,
        detail="Crop recommendations are unavailable because no crop dataset or trained model is installed.",
    )

@app.post("/detailed_analysis/", response_model=DetailedAnalysisResponse)
async def get_detailed_analysis(data: DetailedAnalysisRequest):
    try:
        # Get weather forecast with error handling
        forecast = await get_weather_forecast(data.latitude, data.longitude)
        if not forecast:
            forecast = []  # Use empty list instead of failing
            print("Using empty forecast due to API failure")

        # Get market trends with error handling
        market_history = await get_market_history(data.crop_name)
        if not market_history:
            market_history = []
            print("Using empty market history due to API failure")

        # Create weather forecast graph with improved styling
        weather_dates = [f.date for f in forecast]
        temps = [f.temperature for f in forecast]
        humidity = [f.humidity for f in forecast]
        rainfall = [f.rainfall for f in forecast]

        weather_fig = go.Figure()
        
        # Temperature line with monthly average trendline
        monthly_temps = []
        monthly_dates = []
        for i in range(0, len(temps), 30):
            monthly_temps.append(np.mean(temps[i:i+30]))
            monthly_dates.append(weather_dates[i])

        weather_fig.add_trace(go.Scatter(
            x=weather_dates,
            y=temps,
            name="Daily Temperature",
            line=dict(color="#FF9900", width=1),
            hovertemplate="Temp: %{y}°C<br>Date: %{x}"
        ))
        
        weather_fig.add_trace(go.Scatter(
            x=monthly_dates,
            y=monthly_temps,
            name="Monthly Average",
            line=dict(color="#FF0000", width=2, dash='dash'),
            hovertemplate="Avg Temp: %{y:.1f}°C<br>Month: %{x}"
        ))
        
        # Humidity line
        weather_fig.add_trace(go.Scatter(
            x=weather_dates,
            y=humidity,
            name="Humidity",
            line=dict(color="#00CC96", width=2),
            hovertemplate="Humidity: %{y}%<br>Date: %{x}"
        ))
        
        # Rainfall bars
        weather_fig.add_trace(go.Bar(
            x=weather_dates,
            y=rainfall,
            name="Rainfall",
            marker_color="#636EFA",
            hovertemplate="Rainfall: %{y}mm<br>Date: %{x}"
        ))
        
        # Update layout for 6-month view
        weather_fig.update_layout(
            title="6-Month Weather Forecast",
            xaxis_title="Date",
            yaxis_title="Temperature (°C) / Humidity (%) / Rainfall (mm)",
            hovermode='x unified',
            showlegend=True,
            template="plotly_white",
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=7, label="1w", step="day", stepmode="backward"),
                        dict(count=1, label="1m", step="month", stepmode="backward"),
                        dict(count=3, label="3m", step="month", stepmode="backward"),
                        dict(step="all", label="6m")
                    ])
                )
            )
        )

        # Create market trends graph with improved styling
        market_dates = [m.date for m in market_history]
        prices = [m.price for m in market_history]
        volumes = [m.volume for m in market_history]

        price_fig = go.Figure()
        
        # Price line
        price_fig.add_trace(go.Scatter(
            x=market_dates,
            y=prices,
            name="Price",
            line=dict(color="#FF9900", width=2),
            hovertemplate="Price: ₹%{y:.2f}/kg<br>Date: %{x}"
        ))
        
        # Volume bars
        price_fig.add_trace(go.Bar(
            x=market_dates,
            y=volumes,
            name="Volume",
            marker_color="#636EFA",
            yaxis="y2",
            hovertemplate="Volume: %{y:,} kg<br>Date: %{x}"
        ))
        
        price_fig.update_layout(
            title=f"{data.crop_name} Price Trends",
            xaxis_title="Date",
            yaxis_title="Price (₹/kg)",
            yaxis2=dict(
                title="Volume (kg)",
                overlaying="y",
                side="right"
            ),
            hovermode='x unified',
            showlegend=True,
            template="plotly_white"
        )

        return DetailedAnalysisResponse(
            weather_forecast=forecast,
            market_trends=market_history,
            weather_graph=weather_fig.to_dict(),
            price_graph=price_fig.to_dict()
        )

    except Exception as e:
        print(f"Detailed analysis error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate detailed analysis: {str(e)}"
        )

@app.post("/get_crop_schedule/")
async def get_schedule(data: CropScheduleRequest):
    schedule = get_crop_schedule(data.crop_name, data.state, data.season)
    if schedule:
        return {"schedule": schedule}
    raise HTTPException(
        status_code=503,
        detail="Crop schedule generation is unavailable; check GEMINI_API_KEY and the AI provider.",
    )

@app.get("/get_farmers/")
async def get_farmers(state: str = "", crop: str = "", db: Session = Depends(get_db)):
    try:
        # Get farmers from database
        query = db.query(Farmer)
        
        # Apply filters
        if state:
            query = query.filter(Farmer.state.ilike(f"%{state}%"))
        
        farmers = query.all()
        
        # Convert to list of dictionaries
        farmer_list = []
        for farmer in farmers:
            # Get crops for this farmer
            crops = [
                {
                    "name": "Rice",  # Replace with actual crop data once implemented
                    "season": "Kharif",
                    "expected_yield": 2000,
                    "harvest_date": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
                }
            ]
            
            farmer_dict = {
                "id": farmer.id,
                "name": farmer.name,
                "state": farmer.state,
                "district": "Local",  # Add district to Farmer model if needed
                "phone": "+91 98765 43210",  # Add phone to Farmer model if needed
                "crops": crops
            }
            
            # Filter by crop if specified
            if crop and not any(c["name"].lower() == crop.lower() for c in crops):
                continue
                
            farmer_list.append(farmer_dict)
        
        return farmer_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_season_score(params, current_season):
    # Define season compatibility for different temperature and rainfall ranges
    if current_season == "Summer":
        if 25 <= params['Temperature'] <= 35 and params['Rainfall'] <= 100:
            return 1.0
        return 0.5
    elif current_season == "Monsoon":
        if 20 <= params['Temperature'] <= 30 and params['Rainfall'] >= 100:
            return 1.0
        return 0.5
    elif current_season == "Winter":
        if 15 <= params['Temperature'] <= 25 and params['Rainfall'] <= 50:
            return 1.0
        return 0.5
    else:  # Post-Monsoon
        if 20 <= params['Temperature'] <= 30 and 50 <= params['Rainfall'] <= 100:
            return 1.0
        return 0.5

if __package__:
    from .crop_advisor import get_crop_schedule
    from .models.commodity import CommodityPrice, Base as CommodityBase
    from .models.marketplace import MarketListing, Base as MarketplaceBase
else:
    from crop_advisor import get_crop_schedule
    from models.commodity import CommodityPrice, Base as CommodityBase
    from models.marketplace import MarketListing, Base as MarketplaceBase

@app.post("/detect_disease/")
async def detect_disease(file: UploadFile = File(...)):
    raise HTTPException(
        status_code=503,
        detail="Disease detection is unavailable because no trained disease model is installed.",
    )

# Gemini AI integration
# Load Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


async def get_gemini_response(prompt: str) -> str:
    if gemini_client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    context = """You are KrishiAI, an expert farming assistant. Provide detailed advice about:
        - Crop cultivation and management
        - Pest control and disease prevention
        - Soil health and fertilization
        - Irrigation methods
        - Weather impacts
        - Modern farming technologies
        
        Give practical, actionable advice in simple language.
    """

    full_prompt = f"{context}\n\nQuestion: {prompt}\n\nAnswer:"
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt,
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return response.text

@app.post("/chat/")
async def chat_with_farmer(message: ChatMessage):
    if gemini_client is None:
        raise HTTPException(
            status_code=503,
            detail="AI chat is unavailable because GEMINI_API_KEY is not configured.",
        )
    try:
        response = await get_gemini_response(message.message)
        return {"reply": response}
    except Exception as exc:
        logger.exception("Gemini chat request failed")
        raise HTTPException(status_code=502, detail="Gemini request failed") from exc

# Add after database setup
def load_commodity_data():
    if not COMMODITY_DATA_PATH.is_file():
        logger.warning("Commodity dataset not found at %s; skipping import", COMMODITY_DATA_PATH)
        return

    df = pd.read_csv(COMMODITY_DATA_PATH)
    df["Arrival_Date"] = pd.to_datetime(df["Arrival_Date"], format="%d/%m/%Y")

    CommodityBase.metadata.create_all(bind=engine)
    with SessionLocal.begin() as db:
        if db.query(CommodityPrice).first() is not None:
            return

        for row_number, (_, row) in enumerate(df.iterrows()):
            price = CommodityPrice(
                id=f"{row['State']}_{row['District']}_{row['Market']}_{row['Commodity']}_{row['Arrival_Date'].date()}_{row_number}",
                state=row["State"],
                district=row["District"],
                market=row["Market"],
                commodity=row["Commodity"],
                variety=row["Variety"],
                grade=row["Grade"],
                arrival_date=row["Arrival_Date"].date(),
                min_price=row["Min_x0020_Price"],
                max_price=row["Max_x0020_Price"],
                modal_price=row["Modal_x0020_Price"],
            )
            db.add(price)

# Add new endpoint
@app.get("/commodity_prices/")
async def get_commodity_prices(
    state: str = None,
    commodity: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(CommodityPrice)
    
    if state:
        query = query.filter(CommodityPrice.state == state)
    if commodity:
        query = query.filter(CommodityPrice.commodity == commodity)
    if start_date:
        query = query.filter(CommodityPrice.arrival_date >= start_date)
    if end_date:
        query = query.filter(CommodityPrice.arrival_date <= end_date)
        
    prices = query.all()
    return {
        "prices": [
            {
                "state": p.state,
                "district": p.district,
                "market": p.market,
                "commodity": p.commodity,
                "variety": p.variety,
                "arrival_date": p.arrival_date.strftime("%Y-%m-%d"),
                "min_price": p.min_price,
                "max_price": p.max_price,
                "modal_price": p.modal_price
            }
            for p in prices
        ]
    }

# Import the dataset only when the commodity table is empty.
load_commodity_data()

# Add these imports at the top
import uuid
from datetime import datetime
from typing import Optional

# Add these Pydantic models after other models
class MarketListingCreate(BaseModel):
    seller_name: str  # Changed from farmer_id
    crop_name: str
    quantity: float
    price_per_kg: float
    location: str
    state: str
    contact_number: str
    
    @field_validator('contact_number')  # Changed from @validator
    def validate_phone(cls, v):
        if not v.strip():
            raise ValueError('Contact number is required')
        return v.strip()

class MarketListingResponse(BaseModel):
    id: str
    seller_name: str  # Changed from farmer fields
    crop_name: str
    quantity: float
    price_per_kg: float
    location: str
    state: str
    contact_number: str
    created_at: datetime
    status: str

# Add after database setup code
MarketplaceBase.metadata.create_all(bind=engine)

# Add these new routes
@app.post("/marketplace/list/", response_model=MarketListingResponse)
async def create_listing(
    listing: MarketListingCreate,
    db: Session = Depends(get_db)
):
    try:
        new_listing = MarketListing(
            id=str(uuid.uuid4()),
            seller_name=listing.seller_name,
            crop_name=listing.crop_name,
            quantity=listing.quantity,
            price_per_kg=listing.price_per_kg,
            location=listing.location,
            state=listing.state,
            contact_number=listing.contact_number,
            created_at=datetime.utcnow(),
            status="available"
        )
        
        db.add(new_listing)
        db.commit()
        db.refresh(new_listing)
        
        return {
            "id": new_listing.id,
            "seller_name": new_listing.seller_name,
            "crop_name": new_listing.crop_name,
            "quantity": new_listing.quantity,
            "price_per_kg": new_listing.price_per_kg,
            "location": new_listing.location,
            "state": new_listing.state,
            "contact_number": new_listing.contact_number,
            "created_at": new_listing.created_at,
            "status": new_listing.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/marketplace/listings/")
async def get_listings(
    state: Optional[str] = None,
    crop: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        # Add sample listings if none exist
        if db.query(MarketListing).count() == 0:
            sample_listings = [
                {
                    "seller_name": "Rajesh Kumar",
                    "crop_name": "Rice",
                    "quantity": 1000,
                    "price_per_kg": 25.0,
                    "location": "Patna",
                    "state": "Bihar",
                    "contact_number": "9876543210"
                },
                {
                    "seller_name": "Amit Singh",
                    "crop_name": "Wheat",
                    "quantity": 2000,
                    "price_per_kg": 30.0,
                    "location": "Ludhiana",
                    "state": "Punjab",
                    "contact_number": "9876543211"
                }
            ]
            
            for listing in sample_listings:
                new_listing = MarketListing(
                    id=str(uuid.uuid4()),
                    **listing,
                    created_at=datetime.utcnow(),
                    status="available"
                )
                db.add(new_listing)
            db.commit()

        # Query listings with filters
        query = db.query(MarketListing)
        if state:
            query = query.filter(MarketListing.state.ilike(f"%{state}%"))
        if crop:
            query = query.filter(MarketListing.crop_name.ilike(f"%{crop}%"))
            
        listings = query.all()
        return {"listings": [
            {
                "id": l.id,
                "seller_name": l.seller_name,
                "crop_name": l.crop_name,
                "quantity": l.quantity,
                "price_per_kg": l.price_per_kg,
                "location": l.location,
                "state": l.state,
                "contact_number": l.contact_number,
                "created_at": l.created_at,
                "status": l.status
            } for l in listings
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)