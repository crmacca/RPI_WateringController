import asyncio
from prisma import Prisma
from Plant import Plant
from Weather import get_precipitation_data, get_sunrise_sunset_times
import signal
import sys
from pytz import timezone  # type: ignore
from datetime import datetime
from Optimisation import Optimisation 

AEST = timezone('Australia/Sydney')

db = Prisma()
printSystemLog = True
debug = True  # Debug mode for more detailed logging

def log(message, log_type="GENERIC"):
    """
    Global logging function that immediately prints the log message if printSystemLog is enabled.
    """
    entry = f"[{log_type}] [{datetime.now(AEST).strftime('%Y-%m-%d %H:%M:%S')}] - {message}"
    if printSystemLog:
        print(entry)

async def graceful_shutdown():
    log('Disconnecting from database...', "INFO")
    await db.disconnect()
    log('Disconnected from database. Exiting...', "INFO")
    sys.exit(0)

def signal_handler(sig, frame):
    log('Graceful exit requested. Please wait...', "INFO")
    asyncio.create_task(graceful_shutdown())

class System:

    ## SYSTEM SETUP FUNCTIONS
    def __init__(self):
        # Default settings
        self.check_rate = 60000
        self.operating_settings_desired_moisture_level = 100
        self.operating_settings_water_cycle_length = 20
        self.operating_settings_water_threshold = 20
        self.operating_hours_mode = "auto"
        self.operating_hours_start = "06:00"
        self.operating_hours_end = "18:00"
        self.post_code = 2000
        self.location_code = None
        self.weather_detection_enabled = True
        self.weather_detection_mode = "AND"
        self.weather_detection_postpone_percentage = 35
        self.weather_detection_postpone_mm = 5
        self.danger_mode_enabled = True
        self.danger_mode_level = 10
        self.danger_mode_bypass_enabled = True
        self.danger_mode_bypass_water_percentage = 40
        self.desired_soil_moisture = 100
        self.water_cycle_length = 5
        self.danger_soil_moisture = 20
        self.system_enabled = False
        self.system_setup = False
        self.is_setup = False
        self.cancelRequested = False
        self.allow_optimisation = False  # New setting
        self.optimisation = None  # Will hold the optimisation object
        self.optimisation_data_collected = 0  # Tracks the number of data points collected

        self.plant = None
        self.postponedWater = {
            "postponed": False,
            "postponedAt": None,
            "postponedBy": None
        }
        self.status = "INIT"

    async def fetch_settings(self):
        try:
            settings = await db.settings.find_first()
            if settings is None:
                # Log that default settings are being created
                log("System not set up, creating default settings.", "INFO")

                # Create default settings if none exist
                settings = await db.settings.create(
                    data={
                        "check_rate": self.check_rate,
                        "operating_settings_desired_moisture_level": self.operating_settings_desired_moisture_level,
                        "operating_settings_water_cycle_length": self.operating_settings_water_cycle_length,
                        "operating_settings_water_threshold": self.operating_settings_water_threshold,
                        "operating_hours_mode": self.operating_hours_mode,
                        "operating_hours_start": self.operating_hours_start,
                        "operating_hours_end": self.operating_hours_end,
                        "post_code": self.post_code,
                        "location_code": self.location_code,
                        "weather_detection_enabled": self.weather_detection_enabled,
                        "weather_detection_mode": self.weather_detection_mode,
                        "weather_detection_postpone_percentage": self.weather_detection_postpone_percentage,
                        "weather_detection_postpone_mm": self.weather_detection_postpone_mm,
                        "danger_mode_enabled": self.danger_mode_enabled,
                        "danger_mode_level": self.danger_mode_level,
                        "danger_mode_bypass_enabled": self.danger_mode_bypass_enabled,
                        "danger_mode_bypass_water_percentage": self.danger_mode_bypass_water_percentage,
                        "desired_soil_moisture": self.desired_soil_moisture,
                        "water_cycle_length": self.water_cycle_length,
                        "danger_soil_moisture": self.danger_soil_moisture,
                        "system_enabled": self.system_enabled,
                        "system_setup": self.system_setup,
                        "is_setup": self.is_setup,
                        "allow_optimisation": self.allow_optimisation  # New setting
                    }
                )
            else:
                # Apply settings from the database
                self.check_rate = settings.check_rate
                self.operating_settings_desired_moisture_level = settings.operating_settings_desired_moisture_level
                self.operating_settings_water_cycle_length = settings.operating_settings_water_cycle_length
                self.operating_settings_water_threshold = settings.operating_settings_water_threshold
                self.operating_hours_mode = settings.operating_hours_mode
                self.operating_hours_start = settings.operating_hours_start
                self.operating_hours_end = settings.operating_hours_end
                self.post_code = settings.post_code
                self.location_code = settings.location_code
                self.weather_detection_enabled = settings.weather_detection_enabled
                self.weather_detection_mode = settings.weather_detection_mode
                self.weather_detection_postpone_percentage = settings.weather_detection_postpone_percentage
                self.weather_detection_postpone_mm = settings.weather_detection_postpone_mm
                self.danger_mode_enabled = settings.danger_mode_enabled
                self.danger_mode_level = settings.danger_mode_level
                self.danger_mode_bypass_enabled = settings.danger_mode_bypass_enabled
                self.danger_mode_bypass_water_percentage = settings.danger_mode_bypass_water_percentage
                self.desired_soil_moisture = settings.desired_soil_moisture
                self.water_cycle_length = settings.water_cycle_length
                self.danger_soil_moisture = settings.danger_soil_moisture
                self.system_enabled = settings.system_enabled
                self.system_setup = settings.system_setup
                self.is_setup = settings.is_setup
                self.allow_optimisation = settings.allow_optimisation  # New setting

                # Log that settings were successfully fetched
                log("Settings fetched successfully from the database.", "INFO")
        except Exception as e:
            # Log the error if fetching settings fails
            log(f"Error fetching settings: {str(e)}", "ERROR")
            raise

    async def initialize(self):
        log("Started Initialization Process", "INIT")
        
        # Fetch the system settings from the database
        await self.fetch_settings()

        # Check if the system is set up
        if self.system_setup:
            self.is_setup = True
            log("System is already set up.", "INFO")
        else:
            log("System is not set up.", "INFO")

        # Check if the system is enabled
        if self.system_enabled:
            self.enabled = True
            self.status = "IDLE"
            log("System is enabled. Monitoring started.", "INFO")
            # Start monitoring as the system is enabled
            asyncio.create_task(self.run_loop())
        else:
            self.status = "DISABLED"
            log("System is disabled. Monitoring not started.", "INFO")

        # Create a plant object
        self.plant = Plant(self.desired_soil_moisture)
        # Instantiate the optimisation object
        self.optimisation = Optimisation(self)
        log("Finished Initialization Process", "INIT")

    async def water_plant(self, target_percentage):
        """
        Water the plant to a specific soil moisture percentage, collecting optimisation data.
        """
        try:
            while self.plant.get_soil_moisture() < target_percentage:
                if self.cancelRequested:
                    log("Watering cancelled by user.", "CANCEL")
                    self.disable_system()
                    return

                log(f"Starting watering cycle. Target moisture: {target_percentage}%", "INFO")
                self.plant.pump.turn_on(self.water_cycle_length)

                # Wait for the cycle to complete and soil moisture to stabilize
                await asyncio.sleep(self.water_cycle_length)
                await asyncio.sleep(60)  # Allow up to 1 minute for soil moisture to update

                current_moisture = self.plant.get_soil_moisture()
                if current_moisture >= target_percentage:
                    log(f"Target soil moisture reached: {current_moisture}%", "SUCCESS")
                    break
                else:
                    log(f"Current soil moisture: {current_moisture}%. Continuing to water.", "INFO")

                # Collect optimisation data
                await self.optimisation.collect_data(self.water_cycle_length, current_moisture)

            log("Watering process completed.", "COMPLETE")
        except Exception as e:
            log(f"Error during watering: {str(e)}", "ERROR")
            self.disable_system()

    async def enable_system(self):
        """
        Enable the system, update the database, and set the state to IDLE.
        """
        self.system_enabled = True
        self.status = "IDLE"
        await db.settings.update(
            where={"id": 1},
            data={"system_enabled": True}
        )
        log("System enabled and set to IDLE.", "INFO")
        asyncio.create_task(self.run_loop())

    def disable_system(self):
        self.enabled = False
        self.status = "DISABLED"
        log("System disabled.", "INFO")
        if self.plant and hasattr(self.plant, 'pump') and self.plant.pump:
            self.plant.pump.cancel()

    async def monitor_plant(self):
        """
        Monitoring logic to be implemented here.
        """
        # Example monitoring logic
        current_time = datetime.now(AEST)
        sunrise_time, sunset_time = get_sunrise_sunset_times(db)
        amount_of_rainfall, probability_of_rain = get_precipitation_data(db)

        currentSoilMoisture = self.plant.get_soil_moisture()
        desiredSoilMoisture = self.operating_settings_desired_moisture_level
        triggerAt = (self.operating_settings_water_threshold / 100) * desiredSoilMoisture

        # Operating Hours Management
        if self.operating_hours_mode == 'auto' or self.operating_hours_mode == 'manual':
            if self.danger_mode_enabled and self.danger_mode_bypass_enabled and currentSoilMoisture <= (self.danger_mode_level / 100) * desiredSoilMoisture:
                log(f"Danger mode triggered, operating hours ignored. Watering to {self.danger_mode_bypass_water_percentage}% of desired watering amount", "INFO")
                await self.water_plant(self.danger_mode_bypass_water_percentage)
                return

            if self.operating_hours_mode == 'auto': #Uses sunrise and sunset times, if out of hours, will cancel function
                if current_time < sunrise_time or current_time > sunset_time:
                    log(f"Outside of operating hours. Watering postponed until next day.", "INFO")
                    return
                
            if self.operating_hours_mode == 'manual':
                if current_time < datetime.strptime(self.operating_hours_start, '%H:%M').replace(tzinfo=AEST) or current_time > datetime.strptime(self.operating_hours_end, '%H:%M').replace(tzinfo=AEST):
                    log(f"Outside of operating hours. Watering postponed until next day.", "INFO")
                    return
        
        if self.plant.get_soil_moisture() <= triggerAt:
            if self.weather_detection_enabled:
                if self.weather_detection_mode == "AND":
                    if amount_of_rainfall >= self.weather_detection_postpone_mm and probability_of_rain >= self.weather_detection_postpone_percentage:
                       
                        if self.danger_mode_enabled and self.danger_mode_bypass_enabled and currentSoilMoisture <= (self.danger_mode_level / 100) * desiredSoilMoisture:
                            log(f"Danger mode triggered, watering postponed. Watering to {self.danger_mode_bypass_water_percentage}% of desired watering amount", "INFO")
                            await self.water_plant(self.danger_mode_bypass_water_percentage)
                            return
                        
                        log(f"Rain detected. Postponing watering. Rainfall: {amount_of_rainfall}mm, Probability of rain: {probability_of_rain}%", "INFO")
                        self.postponedWater = {
                            "postponed": True,
                            "postponedAt": current_time,
                            "postponedBy": "Weather Detection"
                        }
                        return
                elif self.weather_detection_mode == "OR":
                    if amount_of_rainfall >= self.weather_detection_postpone_mm or probability_of_rain >= self.weather_detection_postpone_percentage:

                        if self.danger_mode_enabled and self.danger_mode_bypass_enabled and currentSoilMoisture <= (self.danger_mode_level / 100) * desiredSoilMoisture:
                            log(f"Danger mode triggered, watering postponed. Watering to {self.danger_mode_bypass_water_percentage}% of desired watering amount", "INFO")
                            await self.water_plant(self.danger_mode_bypass_water_percentage)
                            return
                

                        log(f"Rain detected. Postponing watering. Rainfall: {amount_of_rainfall}mm, Probability of rain: {probability_of_rain}%", "INFO")
                        self.postponedWater = {
                            "postponed": True,
                            "postponedAt": current_time,
                            "postponedBy": "Weather Detection"
                        }
                        return
            
            # Perform watering if conditions met
            await self.water_plant(triggerAt)

    async def run_loop(self):
        while self.enabled:
            await self.monitor_plant()
            await asyncio.sleep(self.check_rate / 1000)  # Convert milliseconds to seconds
        return

async def connect_db():
    await db.connect()

async def main():
    await connect_db()  # Connect to the database before system initialization
    system = System()
    await system.initialize()

    await asyncio.Event().wait()  # Keeps the loop running indefinitely

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    log('Listening for graceful exit...', "INFO")

    # Start the main async function
    asyncio.run(main())
