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
