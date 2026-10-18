# Nemotron Responses

This directory stores raw Nemotron text output independently of Gemini's response and the local model's inference result.

- `nemotron_response_{session_id}_{timestamp}.txt`: Exact text returned by the final Nemotron estimate interpretation.
- `latest_nemotron_response.txt`: Exact text from the latest successful final Nemotron interpretation.
- `fallback_response_{session_id}_{timestamp}.txt`: Exact Nemotron text used for requirement extraction when Gemini did not return usable text.
- `latest_fallback_response.txt`: Most recent raw Nemotron fallback response.
- `fallback_requirements_{session_id}_{timestamp}.json`: Normalized requirement payload extracted from a Nemotron fallback response.

Nemotron's final interpretation is informational only. Hardware/software numeric estimates continue to come from the hardware price agent and Estimo's local estimation pipeline.
