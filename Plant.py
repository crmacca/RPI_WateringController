import time
import threading

class Plant:
    def __init__(self, initial_soil_moisture):
        self.soil_moisture_level = initial_soil_moisture
        self.pump = Pump(self)
        self.running = True
        self.moisture_depletion_rate = 0.1  # Soil moisture level depletion rate

    def get_soil_moisture(self):
        return self.soil_moisture_level

    def decrease_soil_moisture(self):
        while self.running:
            time.sleep(2)  # Faster depletion for testing, 2 seconds interval
            self.soil_moisture_level -= self.moisture_depletion_rate
            if self.soil_moisture_level < 0:
                self.soil_moisture_level = 0
            print(f"Current soil moisture level: {self.soil_moisture_level}")

    def start(self):
        threading.Thread(target=self.decrease_soil_moisture).start()

class Pump:
    def __init__(self, plant):
        self.plant = plant
        self.is_on = False
        self.cancel_requested = False

    def turn_on(self, duration):
        self.is_on = True
        self.cancel_requested = False
        threading.Thread(target=self._run_pump, args=(duration,)).start()

    def turn_off(self):
        self.is_on = False

    def _run_pump(self, duration):
        start_time = time.time()
        while self.is_on and (time.time() - start_time < duration):
            if self.cancel_requested:
                print("Pump operation cancelled.")
                self.is_on = False
                break
            print("Pump is on... waiting to add water.")
            time.sleep(2)  # Simulating delay before water affects soil moisture

            if not self.cancel_requested:
                self.add_water()
                print(f"Water added. Soil moisture level: {self.plant.get_soil_moisture()}")
        
        self.turn_off()

    def add_water(self):
        if self.is_on:
            self.plant.soil_moisture_level += 0.5  # Increment soil moisture level
            if self.plant.soil_moisture_level > 1.0:
                self.plant.soil_moisture_level = 1.0

    def cancel(self): ##Check if pump is running, if it is, set cancel_requested to True
        if self.is_on:
            self.cancel_requested = True
