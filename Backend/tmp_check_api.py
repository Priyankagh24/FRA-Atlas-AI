import requests
import json

url = 'http://127.0.0.1:8000/openapi.json'
print('requesting', url)
resp = requests.get(url, timeout=10)
print('status', resp.status_code)
try:
    data = resp.json()
    paths = data.get('paths', {})
    print('has_interventions', any('interventions' in p for p in paths))
    print('paths with interventions:', [p for p in paths if 'interventions' in p])
except Exception as e:
    print('json error', e)
    print(resp.text)
