import sys
import os
from pathlib import Path
from PIL import Image, ImageDraw

scratch_dir = Path("scratch")
scratch_dir.mkdir(exist_ok=True)
img_path = scratch_dir / "test_diagram.png"

# Create a sample architecture diagram image with clear text
img = Image.new("RGB", (600, 400), color=(250, 250, 250))
draw = ImageDraw.Draw(img)
draw.rectangle([(20, 20), (580, 380)], outline=(30, 41, 59), width=3)
draw.text((40, 50), "PROJECT ARCHITECTURE: SMART IRRIGATION IOT CONTROLLER", fill=(15, 23, 42))
draw.text((40, 90), "Hardware Components:", fill=(30, 58, 138))
draw.text((60, 120), "1. Microcontroller: ESP32-WROOM-32D Development Board (Qty: 2)", fill=(51, 65, 85))
draw.text((60, 150), "2. Soil Moisture Sensor Capacitive v1.2 (Qty: 4)", fill=(51, 65, 85))
draw.text((60, 180), "3. Submersible 12V DC Water Pump (Qty: 2)", fill=(51, 65, 85))
draw.text((60, 210), "4. 4-Channel 5V Relay Module (Qty: 1)", fill=(51, 65, 85))
draw.text((40, 250), "Software Components & Development:", fill=(30, 58, 138))
draw.text((60, 280), "1. Embedded Firmware (C++/FreeRTOS, MQTT)", fill=(51, 65, 85))
draw.text((60, 310), "2. Cloud Backend API & Web Management Dashboard", fill=(51, 65, 85))
draw.text((60, 340), "3. Mobile Application (React Native / Flutter)", fill=(51, 65, 85))

img.save(img_path)
print(f"Created sample diagram at {img_path}")

# Now test run_gemini_agent with image_path
sys.path.insert(0, str(Path("KLE fest 2/pipeline_app").resolve()))
sys.path.insert(0, str(Path("KLE fest 2/Nvidea").resolve()))
import app

print("Calling run_gemini_agent with image_path...")
out = app.run_gemini_agent(image_path=str(img_path))
print("Gemini extracted HW items:", len(out.get("hardware_requirement", [])))
print("Gemini extracted SW roles:", len(out.get("software_requirement", {}).get("labor_items", [])))
print("Project name:", out.get("software_requirement", {}).get("project_name"))
print("Done!")
