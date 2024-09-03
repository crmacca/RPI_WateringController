from prisma import Prisma
from datetime import datetime
import asyncio

db = Prisma()

class Optimisation:
    def __init__(self, system):
        self.system = system
        self.optimisation_data = []
        self.data_points_required = 10  # Number of data points needed before using optimisation
        self.threshold_tolerance = 0.05  # Tolerance for moisture accuracy

    async def collect_data(self, water_cycle_length, current_moisture):
        """
        Collect data during watering to calculate optimisation.
        """
        initial_moisture = self.system.plant.get_soil_moisture()
        await asyncio.sleep(water_cycle_length)  # Wait for the cycle duration
        await asyncio.sleep(60)  # Allow time for soil moisture to stabilize

        final_moisture = self.system.plant.get_soil_moisture()
        increase = final_moisture - initial_moisture

        if increase > 0:
            water_per_percent = water_cycle_length / increase
            self.optimisation_data.append(water_per_percent)
            self.system.optimisation_data_collected += 1

            self.system.add_log_entry(f"Optimisation data collected: {water_per_percent} seconds per 1% soil moisture.", "INFO")

            if self.system.optimisation_data_collected >= self.data_points_required:
                await self.evaluate_optimisation()
        else:
            self.system.add_log_entry("No increase in soil moisture detected. Data point ignored.", "WARNING")

    async def evaluate_optimisation(self):
        """
        Evaluate collected data and decide if optimisation should be used.
        """
        average_water_per_percent = sum(self.optimisation_data) / len(self.optimisation_data)

        # Check if the data is consistent
        deviations = [abs(x - average_water_per_percent) for x in self.optimisation_data]
        if all(d <= self.threshold_tolerance * average_water_per_percent for d in deviations):
            # Save optimisation data
            await self.save_optimisation_data(average_water_per_percent)
            self.system.add_log_entry("Optimisation data validated and saved.", "SUCCESS")
        else:
            # Ask user whether to use the data
            self.system.add_log_entry("Optimisation data is inconsistent. Manual validation required.", "WARNING")
            # Here you could implement a function to prompt the user or an admin for input

    async def save_optimisation_data(self, water_per_percent):
        """
        Save the optimisation data to the database.
        """
        await db.optimisation_data.upsert(
            where={"id": 1},
            update={"water_per_percent": water_per_percent, "updatedAt": datetime.now()},
            create={"water_per_percent": water_per_percent, "createdAt": datetime.now()}
        )

    async def apply_optimisation(self, target_percentage):
        """
        Use optimisation data to water the plant to the desired moisture level.
        """
        if not self.optimisation_data:
            self.system.add_log_entry("Optimisation data not available. Skipping optimisation.", "ERROR")
            return

        water_per_percent = self.optimisation_data[-1]  # Use the most recent data
        water_needed = (target_percentage - self.system.plant.get_soil_moisture()) * water_per_percent
        water_needed_per_cycle = water_needed / 2  # Break into 2 cycles

        for _ in range(2):
            if self.system.cancelRequested:
                self.system.add_log_entry("Optimisation cancelled by user.", "CANCEL")
                self.system.disable_system()
                return

            self.system.add_log_entry(f"Optimised watering: {water_needed_per_cycle} seconds per cycle.", "INFO")
            self.system.plant.pump.turn_on(water_needed_per_cycle)

            # Wait for cycle to finish and soil moisture to stabilize
            await asyncio.sleep(water_needed_per_cycle)
            await asyncio.sleep(60)

            if self.system.plant.get_soil_moisture() >= target_percentage:
                self.system.add_log_entry("Target soil moisture reached during optimisation.", "SUCCESS")
                break

        self.system.add_log_entry("Optimised watering completed.", "COMPLETE")

