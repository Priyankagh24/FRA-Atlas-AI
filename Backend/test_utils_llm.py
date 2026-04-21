from utils.llm_utils import clean_with_llm, parse_dss_query

print("------ TEST 1: OCR VALIDATION ------")
text1 = "Patta-Holder Name: 123"
print(clean_with_llm(text1))   # name should become ""

print("\n------ TEST 2: VALID OCR ------")
text2 = """
Patta-Holder Name: Ramesh Kumar
Village: Koraput
District: Koraput
State: Odisha
Land Use: house
Total Area Claimed: 2 hectares
"""
print(clean_with_llm(text2))

print("\n------ TEST 3: STATE DETECTION ------")
print(parse_dss_query("Who is eligible in Odisha?"))

print("\n------ TEST 4: DISTRICT + STATE ------")
print(parse_dss_query("Who is eligible in Koraput, Odisha?"))

print("\n------ TEST 5: OUTSIDE STATE ------")
print(parse_dss_query("Who is eligible in Maharashtra?"))