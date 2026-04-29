Step 4 — Set up the virtual environment (in M2's VSCode terminal)

powershellpython -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

Step 5 — Make sure MRAM is running (only needed for spaces ingestion)

Open a separate terminal anywhere and run:
powershellcd C:\Users\jmalime\Downloads\mramTest
npx @cp-metasys/rest-api-mock

Step 6 — Run spaces ingestion
Back in M2's VSCode terminal (with .venv active):

powershellpython backend/ingest_spaces.py

This fetches all 278 spaces from MRAM. Takes 1-2 minutes.

Step 7 — Start M2 server on port 8001
                                    
powershelluvicorn backend.main:app --reload --port 8001


def fetch_space_detail(base_url: str, space_id: str) -> dict:
    url = f"{base_url}/api/v6/spaces/{space_id}"
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0, verify=False) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1)
