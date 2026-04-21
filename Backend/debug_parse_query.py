import sys
import os
sys.path.append(os.getcwd())
from utils.llm_utils import parse_dss_query
queries = [
    'eligible in pm kisan',
    'eligible in PM KISAN',
    'who is eligible for pm kisan',
    'pm kisan eligibility'
]
for q in queries:
    print('QUERY:', q)
    print('PARSED:', parse_dss_query(q))
    print()
