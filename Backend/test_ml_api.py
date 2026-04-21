import requests

url = 'http://127.0.0.1:8000/model/classify-image'

# Test different images
test_cases = [
    (r'c:\FRA-Portal-main\dataset\Forest\Forest_1.jpg', 'Forest'),
    (r'c:\FRA-Portal-main\dataset\Residential\Residential_1.jpg', 'Residential'),
    (r'c:\FRA-Portal-main\dataset\River\River_1.jpg', 'River'),
    (r'c:\FRA-Portal-main\dataset\AnnualCrop\AnnualCrop_1.jpg', 'AnnualCrop')
]

for filepath, expected in test_cases:
    try:
        files = {'file': open(filepath, 'rb')}
        response = requests.post(url, files=files)
        result = response.json()
        print(f'{expected} image: {result["land_use_class"]} ({result["confidence"]:.1%})')
    except Exception as e:
        print(f'Error testing {expected}: {e}')