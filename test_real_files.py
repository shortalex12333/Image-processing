#!/usr/bin/env python3
"""
Real-world testing script for Image Processing Service.
Tests with actual files from the user's system.
"""

import os
import sys
from pathlib import Path

# Test files to process
TEST_FILES = [
    "/Users/celeste7/Documents/yacht-nas/ROOT/05_GALLEY/stoves/force10/manuals/Force10_Gourmet_Galley_Range_Manual.pdf",
    "/Users/celeste7/Desktop/A. Short Resume.pdf",
]

def test_file_validation():
    """Test basic file validation."""
    print("\n" + "="*80)
    print("TEST 1: File Validation")
    print("="*80)

    for file_path in TEST_FILES:
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue

        file_size = os.path.getsize(file_path)
        file_ext = Path(file_path).suffix

        print(f"\n✅ Found: {Path(file_path).name}")
        print(f"   Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        print(f"   Extension: {file_ext}")

        # Check if within limits
        max_size = 15 * 1024 * 1024  # 15MB
        if file_size > max_size:
            print(f"   ⚠️  WARNING: File exceeds 15MB limit")
        else:
            print(f"   ✅ Size OK (within 15MB limit)")


def test_pdf_extraction():
    """Test PDF text extraction."""
    print("\n" + "="*80)
    print("TEST 2: PDF Text Extraction")
    print("="*80)

    try:
        import pdfplumber
    except ImportError:
        print("❌ pdfplumber not installed. Installing...")
        os.system(f"{sys.executable} -m pip install pdfplumber --quiet")
        import pdfplumber

    for file_path in TEST_FILES:
        if not file_path.endswith('.pdf'):
            continue

        if not os.path.exists(file_path):
            continue

        print(f"\nProcessing: {Path(file_path).name}")

        try:
            with pdfplumber.open(file_path) as pdf:
                print(f"   Pages: {len(pdf.pages)}")

                # Extract text from first page
                if len(pdf.pages) > 0:
                    first_page = pdf.pages[0]
                    text = first_page.extract_text()

                    if text:
                        lines = text.split('\n')
                        print(f"   Text lines: {len(lines)}")
                        print(f"\n   First 10 lines:")
                        for i, line in enumerate(lines[:10], 1):
                            print(f"   {i:2d}. {line[:80]}")
                    else:
                        print("   ⚠️  No text extracted (might be image-based PDF)")

                # Try to find tables
                tables = first_page.extract_tables()
                if tables:
                    print(f"\n   ✅ Found {len(tables)} table(s) on first page")
                    for i, table in enumerate(tables, 1):
                        print(f"      Table {i}: {len(table)} rows x {len(table[0]) if table else 0} cols")
                else:
                    print(f"   ℹ️  No tables detected")

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")


def test_ocr_capability():
    """Test if Tesseract OCR is available."""
    print("\n" + "="*80)
    print("TEST 3: Tesseract OCR Availability")
    print("="*80)

    # Check if tesseract is installed
    result = os.system("which tesseract > /dev/null 2>&1")
    if result == 0:
        print("✅ Tesseract is installed")
        os.system("tesseract --version | head -2")
    else:
        print("❌ Tesseract not found")
        print("   Install with: brew install tesseract")


def test_image_processing():
    """Test image processing capabilities."""
    print("\n" + "="*80)
    print("TEST 4: Image Processing Libraries")
    print("="*80)

    # Test PIL/Pillow
    try:
        from PIL import Image
        print("✅ Pillow (PIL) available")
        print(f"   Version: {Image.__version__ if hasattr(Image, '__version__') else 'unknown'}")
    except ImportError:
        print("❌ Pillow not installed")
        print("   Install with: pip install Pillow")

    # Test OpenCV
    try:
        import cv2
        print("✅ OpenCV available")
        print(f"   Version: {cv2.__version__}")
    except ImportError:
        print("❌ OpenCV not installed")
        print("   Install with: pip install opencv-python")


def test_regex_parsing():
    """Test regex parsing patterns."""
    print("\n" + "="*80)
    print("TEST 5: Regex Pattern Matching")
    print("="*80)

    import re

    # Test data that might appear in packing slips
    test_lines = [
        "1  12  ea  MTU-OF-4568  MTU Oil Filter",
        "2   8  pcs KOH-AF-9902  Kohler Air Filter",
        "3  15  EA  MTU-FF-4569  MTU Fuel Filter",
        "Item: 4, Quantity: 20, Unit: each, Part: TEST-123, Desc: Test Part",
    ]

    # Pattern from row_parser.py
    pattern = r'^\s*(\d+)\s+(\d+\.?\d*)\s+(ea|pcs|pc|each|pieces?|unit|units?)\s+([A-Z0-9-]+)\s+(.+?)$'

    print("Testing parsing patterns:")
    for line in test_lines:
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            print(f"\n   ✅ Matched: {line}")
            print(f"      Line: {match.group(1)}, Qty: {match.group(2)}, Unit: {match.group(3)}")
            print(f"      Part#: {match.group(4)}, Desc: {match.group(5)}")
        else:
            print(f"\n   ❌ No match: {line}")


def test_fuzzy_matching():
    """Test fuzzy string matching."""
    print("\n" + "="*80)
    print("TEST 6: Fuzzy String Matching")
    print("="*80)

    try:
        from rapidfuzz import fuzz
        print("✅ RapidFuzz available")

        # Test part number matching
        test_cases = [
            ("MTU-OF-4568", "MTU OF 4568"),
            ("MTU-OF-4568", "MTUOF4568"),
            ("MTU Oil Filter", "MTU OIL FILTER"),
            ("MTU Oil Filter", "Kohler Air Filter"),
        ]

        print("\nFuzzy matching scores:")
        for str1, str2 in test_cases:
            ratio = fuzz.ratio(str1, str2)
            token_sort = fuzz.token_sort_ratio(str1, str2)
            print(f"\n   '{str1}' vs '{str2}'")
            print(f"      Simple ratio: {ratio}/100")
            print(f"      Token sort: {token_sort}/100")
            if token_sort > 80:
                print(f"      ✅ Good match (>80)")
            else:
                print(f"      ❌ Poor match (<80)")

    except ImportError:
        print("❌ RapidFuzz not installed")
        print("   Install with: pip install rapidfuzz")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("REAL-WORLD TESTING - IMAGE PROCESSING SERVICE")
    print("="*80)
    print("\nTesting with actual files from your system...")

    # Run tests
    test_file_validation()
    test_pdf_extraction()
    test_ocr_capability()
    test_image_processing()
    test_regex_parsing()
    test_fuzzy_matching()

    print("\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. If Tesseract not installed: brew install tesseract")
    print("2. Install missing Python packages: pip install -r requirements.txt")
    print("3. Configure .env file with Supabase and OpenAI credentials")
    print("4. Start server: uvicorn src.main:app --reload --port 8001")
    print("5. Test API: curl http://localhost:8001/health")


if __name__ == "__main__":
    main()
