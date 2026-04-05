"""Test the /humanize/stream endpoint locally and print all SSE events."""
import urllib.request
import json

url = "http://127.0.0.1:8000/api/v1/humanize/stream"
payload = json.dumps({
    "text": "AI is transforming education.",
    "style": "academic",
    "intensity_level": "low",
    "language": "vi",
    "simulate_student": False
}).encode()

req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=60) as resp:
    for line in resp:
        decoded = line.decode().strip()
        if decoded.startswith("data: "):
            raw = decoded[6:]
            try:
                data = json.loads(raw)
                print(f"[{data.get('type')}] history_id={data.get('history_id', 'N/A')}")
                if data.get("type") == "complete":
                    print(f"  -> history_id value: {repr(data.get('history_id'))}")
                    print(f"  -> humanized_text length: {len(data.get('humanized_text', ''))}")
            except json.JSONDecodeError:
                print(f"  (non-json): {raw[:100]}")
