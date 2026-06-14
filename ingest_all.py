import os
import requests

folder = "c:/Everything/Important/Projects/to be added/Company Brain/mock_company_data"
url = "http://localhost:8001/api/v1/ingest/file"

count = 0
for filename in os.listdir(folder):
    if filename.endswith(".txt"):
        filepath = os.path.join(folder, filename)
        with open(filepath, "rb") as f:
            files = {"file": (filename, f, "text/plain")}
            response = requests.post(url, files=files)
            if response.status_code == 200:
                print(f"Ingested {filename}")
                count += 1
            else:
                print(f"Failed to ingest {filename}: {response.text}")

print(f"Successfully ingested {count} files into the Company Brain!")
