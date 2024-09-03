import asyncio
from prisma import Prisma
import os
import requests  # type: ignore
from datetime import datetime, timedelta
import pytz  # type: ignore

# Define AEST timezone
AEST = pytz.timezone('Australia/Sydney')

# Function to get the location code based on postcode
def get_location_code(postcode):
    response = requests.get(f'https://api.willyweather.com.au/v2/{os.environ["WILLYWEATHER_KEY"]}/search.json?query={postcode}&limit=1')
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and len(data['data']) > 0:
            return data['data'][0]['id']
    return None

# Function to calculate the average rainfall amount and probability after the current time
def calculate_rainfall(weather_data):
    current_time = datetime.now(AEST)
    days = weather_data['forecasts']['rainfall']['days']

    rainfall_amounts = []
    probabilities = []
    
    for day in days:
        for entry in day['entries']:
            entry_time = datetime.strptime(entry['dateTime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=AEST)
            if entry_time > current_time:
                # Calculate the average of the startRange and endRange as the rainfall amount
                avg_rainfall_amount = (entry['startRange'] + entry['endRange']) / 2
                rainfall_amounts.append(avg_rainfall_amount)
                probabilities.append(entry['probability'])

    if rainfall_amounts and probabilities:
        avg_rainfall = sum(rainfall_amounts) / len(rainfall_amounts)
        avg_probability = sum(probabilities) / len(probabilities)
        return avg_rainfall, avg_probability
    else:
        return 0, 0

# Async function to fetch and store weather data
async def fetch_and_store_weather_data(db):
    system_settings = await db.settings.find_first()
    if system_settings is None:
        return None

    # Fetch rainfall data
    avg_rainfall, avg_probability = await fetch_rainfall_data(db, system_settings)

    # Fetch sunrise/sunset data
    sunrise_time, sunset_time = await fetch_sunrise_sunset_data(db, system_settings)

    if avg_rainfall is not None and sunrise_time is not None and sunset_time is not None:
        await db.weatherdata.delete_many()
        weather_data = await db.weatherdata.create(
            data={
                "postCode": system_settings.postCode,
                "rainfallProbability": avg_probability,  # Store the rainfall probability
                "sunrise": sunrise_time,
                "sunset": sunset_time,
                "createdAt": datetime.now(AEST),
                "mmOfRainfall": avg_rainfall,  # Store the rainfall amount as well
            }
        )
        print("Weather data stored successfully.")
        return weather_data
    else:
        print("Failed to fetch or store weather data.")
        return None

# Async function to fetch rainfall data
async def fetch_rainfall_data(db, system_settings):
    params = {
        "forecasts": ["rainfall"],
        "days": 2,
        "startDate": datetime.now(AEST).strftime("%Y-%m-%d")
    }

    url = f'https://api.willyweather.com.au/v2/{os.environ["WILLYWEATHER_KEY"]}/locations/{system_settings.locationCode}/weather.json'
    print(f"Requesting rainfall data from URL: {url}")

    response = requests.get(url, params=params)
    if response.status_code == 200:
        print('Weather fetched from API')
        rainfall_data = response.json()
        avg_rainfall, avg_probability = calculate_rainfall(rainfall_data)
        return avg_rainfall, avg_probability
    else:
        print(f"Failed to retrieve rainfall data: {response.status_code}")
        return None, None

# Async function to fetch sunrise/sunset data
async def fetch_sunrise_sunset_data(db, system_settings):
    params = {
        "forecasts": ["sunrisesunset"],
        "days": 2,
        "startDate": datetime.now(AEST).strftime("%Y-%m-%d")
    }

    url = f'https://api.willyweather.com.au/v2/{os.environ["WILLYWEATHER_KEY"]}/locations/{system_settings.locationCode}/weather.json'
    print(f"Requesting sunrise/sunset data from URL: {url}")

    response = requests.get(url, params=params)
    if response.status_code == 200:
        sunrise_sunset_data = response.json()
        sunrise_sunset = sunrise_sunset_data['forecasts']['sunrisesunset']['days'][0]['entries'][0]
        sunrise_time = datetime.strptime(sunrise_sunset['riseDateTime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=AEST)
        sunset_time = datetime.strptime(sunrise_sunset['setDateTime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=AEST)
        return sunrise_time, sunset_time
    else:
        print(f"Failed to retrieve sunrise/sunset data: {response.status_code}")
        return None, None

# Async function to get precipitation rate
async def get_precipitation_data(db):

    weather_data = await db.weatherdata.find_first()
    now_aware = datetime.now(AEST)

    if not weather_data or now_aware - weather_data.createdAt > timedelta(hours=1):
        weather_data = await fetch_and_store_weather_data(db)

    if weather_data:
        return weather_data.mmOfRainfall, weather_data.rainfallProbability
    else:
        return None

# Async function to get sunrise and sunset times
async def get_sunrise_sunset_times(db):

    weather_data = await db.weatherdata.find_first()
    now_aware = datetime.now(AEST)

    if not weather_data or now_aware - weather_data.createdAt > timedelta(hours=1):
        weather_data = await fetch_and_store_weather_data(db)

    if weather_data:
        return weather_data.sunrise, weather_data.sunset
    else:
        return None, None
