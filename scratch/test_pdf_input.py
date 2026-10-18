import sys
from pathlib import Path

pdf_bytes = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 480 >>
stream
BT
/F1 14 Tf
50 720 Td
(PROJECT: Cold-Chain Temperature Monitor) Tj
0 -25 Td
(Hardware Components:) Tj
0 -20 Td
(1. Raspberry Pi Pico W - Qty: 5) Tj
0 -20 Td
(2. DS18B20 Waterproof Temperature Sensor - Qty: 10) Tj
0 -20 Td
(3. 0.96 inch I2C OLED Display - Qty: 5) Tj
0 -20 Td
(4. 3.7V 1200mAh LiPo Battery - Qty: 5) Tj
0 -30 Td
(Software Development Scope:) Tj
0 -20 Td
(1. Firmware MicroPython telemetry) Tj
0 -20 Td
(2. Cloud Ingestion API and TimescaleDB) Tj
0 -20 Td
(3. Mobile Alert Dashboard) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000228 00000 n 
0000000760 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
829
%%EOF
"""

pdf_path = Path("scratch/test_project.pdf")
pdf_path.write_bytes(pdf_bytes)

import pypdf
reader = pypdf.PdfReader(str(pdf_path))
extracted = "\n".join(p.extract_text() for p in reader.pages)
print("Extracted text from PDF:")
print(extracted)

# Now test run_gemini_agent with pdf_path
sys.path.insert(0, str(Path("KLE fest 2/pipeline_app").resolve()))
sys.path.insert(0, str(Path("KLE fest 2/Nvidea").resolve()))
import app

print("\nCalling run_gemini_agent with pdf_path...")
out = app.run_gemini_agent(pdf_path=str(pdf_path))
print("Gemini extracted HW items:", len(out.get("hardware_requirement", [])))
print("Gemini extracted SW roles:", len(out.get("software_requirement", {}).get("labor_items", [])))
print("Project name:", out.get("software_requirement", {}).get("project_name"))
print("Done!")
