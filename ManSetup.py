import asyncio
from prisma import Prisma
import os

async def setup():
    # Initialize Prisma client
    db = Prisma()
    await db.connect()

    # Check if settings already exist
    existing_settings = await db.settings.find_first()

    if existing_settings is not None:
        print("Settings already exist in the database.")
        await db.disconnect()
        return

    # Ask for user input or accept default values
    print("Setup your system settings:")

    desired_soil_moisture = input("Desired Soil Moisture (default 100): ") or 100
    water_cycle_length = input("Water Cycle Length in seconds (default 5): ") or 5
    danger_soil_moisture = input("Danger Soil Moisture level (default 20): ") or 20
    system_enabled = input("Enable the system? (yes/no, default no): ").lower() or "no"
    post_code = input("Enter the postcode (default 2000): ") or 2000

    # Convert input to proper types
    desired_soil_moisture = float(desired_soil_moisture)
    water_cycle_length = float(water_cycle_length)
    danger_soil_moisture = float(danger_soil_moisture)
    system_enabled = system_enabled == "yes"
    post_code = int(post_code)

    # Insert new settings into the database
    new_settings = await db.settings.create(
        data={
            "desiredSoilMoisture": desired_soil_moisture,
            "waterCycleLength": water_cycle_length,
            "dangerSoilMoisture": danger_soil_moisture,
            "systemEnabled": system_enabled,
            "postCode": post_code,
            "systemSetup": True
        }
    )

    print("System settings have been configured:")
    print(f"  Desired Soil Moisture: {new_settings.desiredSoilMoisture}")
    print(f"  Water Cycle Length: {new_settings.waterCycleLength}")
    print(f"  Danger Soil Moisture: {new_settings.dangerSoilMoisture}")
    print(f"  System Enabled: {new_settings.systemEnabled}")
    print(f"  Postcode: {new_settings.postCode}")

    await db.disconnect()

# Run the setup function
if __name__ == "__main__":
    asyncio.run(setup())
