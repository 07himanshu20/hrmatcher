#!/usr/bin/env python
"""
Test script for date filtering functionality
"""
import os
import django
from datetime import datetime, timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hrmatcher.settings')
django.setup()

def test_date_format_conversion():
    """Test date format conversion for IMAP"""
    
    # Test cases
    test_dates = [
        ('2025-09-05', '05-Sep-2025'),
        ('2025-01-15', '15-Jan-2025'),
        ('2025-12-31', '31-Dec-2025'),
        ('2024-02-29', '29-Feb-2024'),  # Leap year
    ]
    
    print("Testing date format conversion:")
    print("-" * 40)
    
    for date_input, expected_output in test_dates:
        try:
            # Convert date string to IMAP format (DD-Mon-YYYY)
            parsed_date = datetime.strptime(date_input, '%Y-%m-%d')
            formatted_date = parsed_date.strftime('%d-%b-%Y')
            
            status = "✓ PASS" if formatted_date == expected_output else "✗ FAIL"
            print(f"{date_input} -> {formatted_date} [{status}]")
            
            if formatted_date != expected_output:
                print(f"  Expected: {expected_output}")
                
        except Exception as e:
            print(f"{date_input} -> ERROR: {e}")
    
    print("\nTesting BEFORE date logic (inclusive):")
    print("-" * 40)
    
    # Test BEFORE date logic
    to_date = '2025-09-05'
    parsed_to_date = datetime.strptime(to_date, '%Y-%m-%d')
    to_date_inclusive = parsed_to_date + timedelta(days=1)
    formatted_before_date = to_date_inclusive.strftime('%d-%b-%Y')
    
    print(f"Input to_date: {to_date}")
    print(f"BEFORE date (inclusive): {formatted_before_date}")
    print(f"This will include emails up to and including {to_date}")

def test_search_query_construction():
    """Test IMAP search query construction"""
    
    print("\n\nTesting IMAP search query construction:")
    print("-" * 40)
    
    # Test different combinations
    test_cases = [
        ('2025-09-01', '2025-09-05'),
        ('2025-09-01', None),
        (None, '2025-09-05'),
        (None, None),
    ]
    
    for date_from, date_to in test_cases:
        search_criteria = []
        
        if date_from:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            formatted_from_date = from_date.strftime('%d-%b-%Y')
            search_criteria.append(f'SINCE {formatted_from_date}')
        
        if date_to:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            to_date_inclusive = to_date + timedelta(days=1)
            formatted_to_date = to_date_inclusive.strftime('%d-%b-%Y')
            search_criteria.append(f'BEFORE {formatted_to_date}')
        
        if search_criteria:
            search_query = ' '.join(search_criteria)
            print(f"From: {date_from}, To: {date_to}")
            print(f"Query: '{search_query}'")
        else:
            print(f"From: {date_from}, To: {date_to}")
            print(f"Query: 'ALL'")
        print()

if __name__ == "__main__":
    test_date_format_conversion()
    test_search_query_construction()
    print("\nDate filtering tests completed!")
