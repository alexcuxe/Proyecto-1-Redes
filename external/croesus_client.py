# external/croesus_client.py
# Simple Croesus (SKF) API client. Comments in simple English.
import os, requests
from typing import Dict, Any, List

BASE_URL = "https://skf-api-external-eu20-tyvvw4iy.prod.apimanagement.eu20.hana.ondemand.com/v1/croesusSearch/main"

class CroesusClient:
    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        self.api_key = api_key or os.getenv("CROESUS_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing CROESUS_API_KEY environment variable.")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"apikey": self.api_key})

    def search(self, brand_code: str, non_skf_designation: str) -> List[Dict[str, Any]]:
        """Call Croesus GET /main and return list of hits."""
        params = {
            "brand_code": brand_code.strip(),
            "non_skf_designation": non_skf_designation.strip(),
        }
        r = self.session.get(BASE_URL, params=params, timeout=self.timeout)
        if r.status_code == 401:
            raise RuntimeError("Unauthorized (401): Invalid API key.")
        if r.status_code == 400:
            raise RuntimeError(f"Bad Request (400): {r.text}")
        r.raise_for_status()
        data = r.json()
        # Expect an array of hits per Swagger
        return data if isinstance(data, list) else []
