# Gemini Responses Directory

This directory stores the exact unparsed response text and the normalized requirements extracted from incoming project requests (text descriptions, architecture diagram images, or project specification PDFs).

### Raw Response Files
- `gemini_response_{session_id}_{timestamp}.txt`: Exact response text returned by the provider, before JSON parsing, repair, or default insertion.
- `latest_gemini_response.txt`: Exact raw text from the most recent response.

Raw text files contain no added JSON wrapper or metadata. A Gemini response is saved whenever one is received. If Gemini fails and Nemotron supplies the requirement response, the raw Nemotron response is kept separately in `../nemotron_responses/`.

### Normalized JSON Files
- `gemini_response_{session_id}_{timestamp}.json`: Parsed and normalized requirements used by the estimation pipeline.
- `latest_gemini_response.json`: Most recently normalized response.

The normalized files contain:
- `hardware_requirement`: List of physical components, specifications, quantities, and recommended hardware models.
- `software_requirement`: Full-scope engineering payload conforming to the estimation engine (project name, currency, software BOM licenses, engineering labor roles with hours and hourly rates, statutory markup rules, ML features, target metric, and analogy dataset ID).
