"""Shared domain core for the Magnum Context-Aware Commerce POC.

Both the synthetic data generator and the API import from here, so the
simulated world and the live decision policies cannot drift apart.
"""

SEED = 20260901
POLICY_VERSION = "policy-v1.0.0"
FORECAST_VERSION = "forecast-baseline-v1.0.0"
GENERATOR_VERSION = "gen-v1.0.0"
CURRENCY = "USD"
