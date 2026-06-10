"""AI triage agent with deterministic guardrails.

The LLM (triage.py) only extracts a free-text request into a structured form and
its output is treated as untrusted. The verdict is decided by deterministic code
(guardrails.py) from the extracted fields, fails closed, and the package has no
import path to the export runner -- so the agent can draft but never release data.
"""
