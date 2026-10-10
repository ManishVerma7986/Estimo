# database/db_writer.py
import json
import os
import sqlite3


def save_engine_output(project_text, input_type, engine_json):
    db_path = os.path.join(os.path.dirname(__file__), "cost_estimator.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Save the project
    cursor.execute(
        "INSERT INTO projects (project_text, input_type) VALUES (?, ?)",
        (project_text, input_type),
    )
    project_id = cursor.lastrowid

    # 2. Extract data from Team 1's JSON structure
    prediction = engine_json.get("prediction", {})
    gemini = engine_json.get("gemini", {})
    hardware = engine_json.get("hardware", {})
    software = engine_json.get("software", {})

    total_cost = prediction.get("total_cost_inr", {})
    hw_cost = prediction.get("hardware_cost_inr", {})
    sw_cost = prediction.get("software_dev_cost_inr", {})
    lic_cost = prediction.get("licence_cost_inr", {})
    effort = prediction.get("effort_months", {})

    all_sources = hardware.get("all_sources", []) + software.get("all_sources", [])

    # 3. Insert into estimates
    cursor.execute(
        """
        INSERT INTO estimates (
            project_id, total_cost_optimistic, total_cost_likely, total_cost_pessimistic,
            hardware_cost_min, hardware_cost_max, software_dev_cost_min, software_dev_cost_max,
            licence_cost_min, licence_cost_max, effort_months_low, effort_months_likely,
            effort_months_high, confidence, summary, hw_items_json, sw_items_json, team_json, sources_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            project_id,
            total_cost.get("optimistic", 0),
            total_cost.get("likely", 0),
            total_cost.get("pessimistic", 0),
            hw_cost.get("min", 0),
            hw_cost.get("max", 0),
            sw_cost.get("min", 0),
            sw_cost.get("max", 0),
            lic_cost.get("min", 0),
            lic_cost.get("max", 0),
            effort.get("low", 0),
            effort.get("likely", 0),
            effort.get("high", 0),
            prediction.get("confidence", "medium"),
            prediction.get("summary", ""),
            json.dumps(gemini.get("hw_items", [])),
            json.dumps(gemini.get("sw_items", [])),
            json.dumps(gemini.get("team", [])),
            json.dumps(all_sources),
        ),
    )

    conn.commit()
    conn.close()
    print(f"Successfully saved estimate for project ID {project_id} to the database.")
    return project_id


if __name__ == "__main__":
    # This is a mock of the exact JSON Team 1's app outputs.
    # You will replace this with the real JSON copied from the browser.
    real_team1_output = {
        "session_id": "60e9fbaab58f7501",
        "gemini": {
            "confidence": "high",
            "hw_items": [
                {
                    "name": "Microcontroller Board",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "ESP32-WROOM-32 Wi-Fi and Bluetooth module with integrated flash",
                    "suggested_models": [
                        {
                            "maker": "Espressif Systems",
                            "model": "ESP32 DevKitC",
                            "why": "Reliable Wi-Fi connectivity and ample GPIOs for sensors and relays",
                        },
                        {
                            "maker": "Adafruit",
                            "model": "ESP32 Feather V2",
                            "why": "Great community support and built-in LiPo battery charging circuit",
                        },
                    ],
                },
                {
                    "name": "Soil Moisture Sensor",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "Capacitive soil moisture sensor, 3.3V to 5V operating voltage, corrosion resistant",
                    "suggested_models": [
                        {
                            "maker": "DFRobot",
                            "model": "SEN0193",
                            "why": "Capacitive design prevents corrosion issues common in resistive sensors",
                        },
                        {
                            "maker": "Adafruit",
                            "model": "Stemma Soil Sensor",
                            "why": "I2C interface allows daisy-chaining multiple sensors easily",
                        },
                    ],
                },
                {
                    "name": "Water Pump",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "12V DC submersible water pump, flow rate ~200-300 L/h",
                    "suggested_models": [
                        {
                            "maker": "Generic",
                            "model": "R385 12V DC Diaphragm Pump",
                            "why": "Provides sufficient pressure and flow for small to medium garden setups",
                        },
                        {
                            "maker": "Uxcell",
                            "model": "AQU-01 Mini Submersible Pump",
                            "why": "Compact and quiet for reservoir integration",
                        },
                    ],
                },
                {
                    "name": "Relay Module",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "1-Channel 5V/12V relay module with optocoupler isolation",
                    "suggested_models": [
                        {
                            "maker": "SunFounder",
                            "model": "1-Channel 12V Relay Module",
                            "why": "Safely isolates the low-voltage ESP32 from the high-current water pump",
                        },
                        {
                            "maker": "Keyestudio",
                            "model": "KS0018 5V Relay",
                            "why": "Easy integration with standard jumper wires",
                        },
                    ],
                },
                {
                    "name": "Power Supply Unit",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "12V 2A DC switching power supply adapter with barrel jack",
                    "suggested_models": [
                        {
                            "maker": "Mean Well",
                            "model": "RS-25-12",
                            "why": "Industrial-grade reliability for continuous operation",
                        },
                        {
                            "maker": "Generic",
                            "model": "12V 2A Power Adapter",
                            "why": "Cost-effective power source for both pump and step-down regulator",
                        },
                    ],
                },
                {
                    "name": "DC-DC Buck Converter",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "LM2596 step-down module, input 4.5V-40V to output 1.5V-35V adjustable",
                    "suggested_models": [
                        {
                            "maker": "DROK",
                            "model": "LM2596 Buck Converter",
                            "why": "Steps down the 12V main supply to a stable 5V/3.3V for the ESP32",
                        }
                    ],
                },
                {
                    "name": "Enclosure Box",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "IP65 weatherproof junction box, ABS plastic with transparent cover",
                    "suggested_models": [
                        {
                            "maker": "Zhejiang",
                            "model": "GAOHE IP65 Junction Box",
                            "why": "Protects electronics from outdoor elements and moisture",
                        },
                        {
                            "maker": "Bud Industries",
                            "model": "PN-1324",
                            "why": "Durable polycarbonate housing with easy mounting options",
                        },
                    ],
                },
            ],
            "sw_items": [],
            "team": [
                {
                    "role": "Embedded Firmware Engineer",
                    "reason": "Programs the ESP32 in C++/MicroPython to read sensors, handle Wi-Fi, and actuate pumps.",
                },
                {
                    "role": "Full-Stack Web Developer",
                    "reason": "Builds the React dashboard and backend API for real-time monitoring and manual controls.",
                },
                {
                    "role": "IoT / Cloud Infrastructure Engineer",
                    "reason": "Sets up MQTT broker, database storage, and secure cloud connectivity for remote device management.",
                },
                {
                    "role": "Hardware / Systems Architect",
                    "reason": "Selects compatible electrical components, designs power distribution, and ensures system safety.",
                },
                {
                    "role": "QA & Test Engineer",
                    "reason": "Validates sensor calibration, long-term outdoor reliability, and end-to-end automation workflows.",
                },
            ],
            "all_items": [
                {
                    "name": "Microcontroller Board",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "ESP32-WROOM-32 Wi-Fi and Bluetooth module with integrated flash",
                    "suggested_models": [
                        {
                            "maker": "Espressif Systems",
                            "model": "ESP32 DevKitC",
                            "why": "Reliable Wi-Fi connectivity and ample GPIOs for sensors and relays",
                        },
                        {
                            "maker": "Adafruit",
                            "model": "ESP32 Feather V2",
                            "why": "Great community support and built-in LiPo battery charging circuit",
                        },
                    ],
                },
                {
                    "name": "Soil Moisture Sensor",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "Capacitive soil moisture sensor, 3.3V to 5V operating voltage, corrosion resistant",
                    "suggested_models": [
                        {
                            "maker": "DFRobot",
                            "model": "SEN0193",
                            "why": "Capacitive design prevents corrosion issues common in resistive sensors",
                        },
                        {
                            "maker": "Adafruit",
                            "model": "Stemma Soil Sensor",
                            "why": "I2C interface allows daisy-chaining multiple sensors easily",
                        },
                    ],
                },
                {
                    "name": "Water Pump",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "12V DC submersible water pump, flow rate ~200-300 L/h",
                    "suggested_models": [
                        {
                            "maker": "Generic",
                            "model": "R385 12V DC Diaphragm Pump",
                            "why": "Provides sufficient pressure and flow for small to medium garden setups",
                        },
                        {
                            "maker": "Uxcell",
                            "model": "AQU-01 Mini Submersible Pump",
                            "why": "Compact and quiet for reservoir integration",
                        },
                    ],
                },
                {
                    "name": "Relay Module",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "1-Channel 5V/12V relay module with optocoupler isolation",
                    "suggested_models": [
                        {
                            "maker": "SunFounder",
                            "model": "1-Channel 12V Relay Module",
                            "why": "Safely isolates the low-voltage ESP32 from the high-current water pump",
                        },
                        {
                            "maker": "Keyestudio",
                            "model": "KS0018 5V Relay",
                            "why": "Easy integration with standard jumper wires",
                        },
                    ],
                },
                {
                    "name": "Power Supply Unit",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "12V 2A DC switching power supply adapter with barrel jack",
                    "suggested_models": [
                        {
                            "maker": "Mean Well",
                            "model": "RS-25-12",
                            "why": "Industrial-grade reliability for continuous operation",
                        },
                        {
                            "maker": "Generic",
                            "model": "12V 2A Power Adapter",
                            "why": "Cost-effective power source for both pump and step-down regulator",
                        },
                    ],
                },
                {
                    "name": "DC-DC Buck Converter",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "LM2596 step-down module, input 4.5V-40V to output 1.5V-35V adjustable",
                    "suggested_models": [
                        {
                            "maker": "DROK",
                            "model": "LM2596 Buck Converter",
                            "why": "Steps down the 12V main supply to a stable 5V/3.3V for the ESP32",
                        }
                    ],
                },
                {
                    "name": "Enclosure Box",
                    "discipline": "HW",
                    "kind": "buy",
                    "options": [],
                    "spec": "IP65 weatherproof junction box, ABS plastic with transparent cover",
                    "suggested_models": [
                        {
                            "maker": "Zhejiang",
                            "model": "GAOHE IP65 Junction Box",
                            "why": "Protects electronics from outdoor elements and moisture",
                        },
                        {
                            "maker": "Bud Industries",
                            "model": "PN-1324",
                            "why": "Durable polycarbonate housing with easy mounting options",
                        },
                    ],
                },
            ],
            "input_type": "text",
        },
        "hardware": {
            "items": [
                {
                    "name": "Water Pump",
                    "spec": "12V DC submersible water pump, flow rate ~200-300 L/h",
                    "suggested_models": [
                        {
                            "maker": "Generic",
                            "model": "R385 12V DC Diaphragm Pump",
                            "why": "Provides sufficient pressure and flow for small to medium garden setups",
                        },
                        {
                            "maker": "Uxcell",
                            "model": "AQU-01 Mini Submersible Pump",
                            "why": "Compact and quiet for reservoir integration",
                        },
                    ],
                    "price_summary": {},
                    "source_count": 0,
                    "sources": [],
                },
                {
                    "name": "Soil Moisture Sensor",
                    "spec": "Capacitive soil moisture sensor, 3.3V to 5V operating voltage, corrosion resistant",
                    "suggested_models": [
                        {
                            "maker": "DFRobot",
                            "model": "SEN0193",
                            "why": "Capacitive design prevents corrosion issues common in resistive sensors",
                        },
                        {
                            "maker": "Adafruit",
                            "model": "Stemma Soil Sensor",
                            "why": "I2C interface allows daisy-chaining multiple sensors easily",
                        },
                    ],
                    "price_summary": {},
                    "source_count": 0,
                    "sources": [],
                },
                {
                    "name": "Relay Module",
                    "spec": "1-Channel 5V/12V relay module with optocoupler isolation",
                    "suggested_models": [
                        {
                            "maker": "SunFounder",
                            "model": "1-Channel 12V Relay Module",
                            "why": "Safely isolates the low-voltage ESP32 from the high-current water pump",
                        },
                        {
                            "maker": "Keyestudio",
                            "model": "KS0018 5V Relay",
                            "why": "Easy integration with standard jumper wires",
                        },
                    ],
                    "price_summary": {},
                    "source_count": 0,
                    "sources": [],
                },
                {
                    "name": "Microcontroller Board",
                    "spec": "ESP32-WROOM-32 Wi-Fi and Bluetooth module with integrated flash",
                    "suggested_models": [
                        {
                            "maker": "Espressif Systems",
                            "model": "ESP32 DevKitC",
                            "why": "Reliable Wi-Fi connectivity and ample GPIOs for sensors and relays",
                        },
                        {
                            "maker": "Adafruit",
                            "model": "ESP32 Feather V2",
                            "why": "Great community support and built-in LiPo battery charging circuit",
                        },
                    ],
                    "price_summary": {},
                    "source_count": 0,
                    "sources": [],
                },
                {
                    "name": "DC-DC Buck Converter",
                    "spec": "LM2596 step-down module, input 4.5V-40V to output 1.5V-35V adjustable",
                    "suggested_models": [
                        {
                            "maker": "DROK",
                            "model": "LM2596 Buck Converter",
                            "why": "Steps down the 12V main supply to a stable 5V/3.3V for the ESP32",
                        }
                    ],
                    "price_summary": {},
                    "source_count": 0,
                    "sources": [],
                },
                {
                    "name": "Power Supply Unit",
                    "spec": "12V 2A DC switching power supply adapter with barrel jack",
                    "suggested_models": [
                        {
                            "maker": "Mean Well",
                            "model": "RS-25-12",
                            "why": "Industrial-grade reliability for continuous operation",
                        },
                        {
                            "maker": "Generic",
                            "model": "12V 2A Power Adapter",
                            "why": "Cost-effective power source for both pump and step-down regulator",
                        },
                    ],
                    "price_summary": {},
                    "source_count": 0,
                    "sources": [],
                },
                {
                    "name": "Enclosure Box",
                    "spec": "IP65 weatherproof junction box, ABS plastic with transparent cover",
                    "suggested_models": [
                        {
                            "maker": "Zhejiang",
                            "model": "GAOHE IP65 Junction Box",
                            "why": "Protects electronics from outdoor elements and moisture",
                        },
                        {
                            "maker": "Bud Industries",
                            "model": "PN-1324",
                            "why": "Durable polycarbonate housing with easy mounting options",
                        },
                    ],
                    "price_summary": {},
                    "source_count": 0,
                    "sources": [],
                },
            ],
            "total": {"min": 0, "max": 0},
            "all_sources": [],
            "source_count": 0,
        },
        "software": {"items": [], "effort": {}, "licence_cost": {}},
        "prediction": {
            "total_cost_inr": {
                "optimistic": 45000,
                "likely": 65000,
                "pessimistic": 90000,
            },
            "hardware_cost_inr": {"min": 2500, "max": 5000},
            "software_dev_cost_inr": {"min": 40000, "max": 60000},
            "licence_cost_inr": {"min": 0, "max": 0},
            "effort_months": {"low": 1, "likely": 2, "high": 3},
            "duplicates_flagged": [],
            "missing_specs": [
                "Exact pricing data for specific hardware models was missing from live feeds, requiring estimation based on market averages.",
                "Power supply specifics (e.g., solar vs. mains) are not fully detailed.",
            ],
            "confidence": "high",
            "summary": "The project cost is primarily driven by software development and engineering effort across embedded, full-service web, and IoT domains, totaling an estimated 2 months of work. Hardware costs remain relatively low, centered around standard microcontrollers, sensors, and pumps. Overall, the expected investment falls around 65,000 INR.",
        },
    }

    save_engine_output(
        project_text="Build a smart irrigation system with ESP32",
        input_type="text",
        engine_json=real_team1_output,
    )
