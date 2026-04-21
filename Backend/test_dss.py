#!/usr/bin/env python3
"""
Test script for DSS query functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.llm_utils import parse_dss_query
from services.scheme_service import find_eligible_people_by_scheme
from db import get_scheme_by_name

def test_dss_parsing():
    """Test the DSS query parsing functionality"""
    test_queries = [
        # Basic scheme queries
        "Who is eligible for MGNREGA in Odisha?",
        "Show me people eligible for Farm Support Scheme in Koraput",
        "Who can get PM Kisan in Maharashtra?",

        # Location-only queries
        "Who is eligible in Odisha?",
        "Show claims in Koraput district",
        "People in Maharashtra",

        # Edge cases
        "mgnrega in odisha",  # lowercase
        "FARM SUPPORT SCHEME IN KORAPUT",  # uppercase
        "  MGNREGA    in   Odisha  ",  # extra spaces

        # Invalid/out-of-scope queries
        "What is the weather today?",
        "How to cook pasta?",
        "Buy groceries online",
        "Tell me a joke",
        "abc123",  # random text
        "",  # empty
        "   ",  # whitespace only

        # Spelling mistakes
        "Who is eligible for MGNREGA in Odissa?",  # misspelled Odisha
        "Farm suport scheme in Koraput",  # misspelled support
        "PM Kisan in Maharastra",  # misspelled Maharashtra

        # Unsupported states
        "Who is eligible for MGNREGA in California?",
        "Farm scheme in Texas",

        # Natural language queries
        "I want to know about government schemes in Odisha",
        "Can you tell me who gets farm support in Koraput?",
        "Looking for MGNREGA beneficiaries in Maharashtra"
    ]

    print("Testing DSS Query Parsing:")
    print("=" * 50)

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        try:
            parsed = parse_dss_query(query)
            print(f"Parsed: {parsed}")
        except Exception as e:
            print(f"Error: {e}")

def test_scheme_service():
    """Test the scheme service functionality"""
    print("\n\nTesting Scheme Service:")
    print("=" * 50)

    # Test scheme lookup
    schemes_to_test = ["MGNREGA", "Farm Support Scheme", "PM Kisan", "Invalid Scheme"]

    for scheme_name in schemes_to_test:
        print(f"\nTesting scheme: '{scheme_name}'")
        try:
            scheme = get_scheme_by_name(scheme_name)
            if scheme:
                print(f"Found scheme: {scheme}")
            else:
                print("Scheme not found")
        except Exception as e:
            print(f"Error: {e}")

    # Test location-only query (if database is available)
    print("\nTesting location-only query:")
    try:
        results = find_eligible_people_by_scheme(
            scheme=None,
            village=None,
            district="Koraput",
            state="Odisha"
        )
        print(f"Found {len(results)} results for Koraput, Odisha")
    except Exception as e:
        print(f"Database error (expected if DB not set up): {e}")

if __name__ == "__main__":
    test_dss_parsing()
    test_scheme_service()