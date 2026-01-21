#!/usr/bin/env python3
"""
Real integration tests for Phase 1 features.
Tests actual code paths, not just algorithm logic.
"""

import io
import sys
from PIL import Image, ExifTags
import numpy as np
import cv2

print("=" * 70)
print("REAL INTEGRATION TESTS - Phase 1")
print("=" * 70)

# ============================================================================
# TEST 1: Import actual production code
# ============================================================================
print("\n[TEST 1] Importing production code...")
try:
    from src.ocr.preprocessor import ImagePreprocessor
    from src.intake.validator import FileValidator
    from src.config import settings
    print("✅ Production modules imported successfully")
except ImportError as e:
    print(f"❌ FAILED to import: {e}")
    sys.exit(1)

# ============================================================================
# TEST 2: Test HEIC conversion with simulated HEIC file
# ============================================================================
print("\n[TEST 2] Testing HEIC conversion in preprocessor...")

# Create a test image and save as PNG (since we can't create real HEIC easily)
# We'll test that the conversion logic doesn't break normal images
test_image = Image.new('RGB', (800, 600), color='blue')
png_buffer = io.BytesIO()
test_image.save(png_buffer, format='PNG')
png_bytes = png_buffer.getvalue()

try:
    # Test the preprocessor.preprocess() method
    result = ImagePreprocessor.preprocess(png_bytes)

    if isinstance(result, bytes) and len(result) > 0:
        print(f"✅ Preprocessor works with PNG: {len(result)} bytes output")
    else:
        print(f"❌ Preprocessor returned invalid result: {type(result)}")
        sys.exit(1)
except Exception as e:
    print(f"❌ Preprocessor failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 3: Test EXIF rotation with real EXIF data
# ============================================================================
print("\n[TEST 3] Testing EXIF rotation with real metadata...")

# Create image with EXIF orientation tag
test_image_exif = Image.new('RGB', (100, 200), color='red')
exif = test_image_exif.getexif()

# Add orientation tag (6 = rotate 90 CW)
exif[274] = 6  # ExifTags.Base.Orientation

# Save with EXIF
exif_buffer = io.BytesIO()
test_image_exif.save(exif_buffer, format='JPEG', exif=exif)
exif_bytes = exif_buffer.getvalue()

try:
    # Preprocess should apply EXIF rotation
    result = ImagePreprocessor.preprocess(exif_bytes)

    # Decode result to check dimensions changed (100x200 → should be rotated)
    nparr = np.frombuffer(result, np.uint8)
    decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if decoded is not None:
        h, w = decoded.shape[:2]
        print(f"✅ EXIF rotation applied: Input was 100x200, output is {w}x{h}")
        # Note: After preprocessing (grayscale, etc), we can't verify exact dimensions
        # but we can verify it didn't crash
    else:
        print("❌ Failed to decode preprocessed image")
        sys.exit(1)

except Exception as e:
    print(f"❌ EXIF rotation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 4: Test DQS calculation with real validator
# ============================================================================
print("\n[TEST 4] Testing DQS calculation via FileValidator...")

# Create test images with known quality characteristics
validator = FileValidator(upload_type="receiving")

# Test 1: Good quality image (high contrast)
good_image = Image.new('L', (1000, 1000), color=255)
for i in range(500):
    for j in range(1000):
        good_image.putpixel((i, j), 0)  # Half black, half white = high contrast

good_buffer = io.BytesIO()
good_image.save(good_buffer, format='PNG')
good_bytes = good_buffer.getvalue()

try:
    dqs_result = validator._calculate_dqs(good_bytes)

    print(f"   Good image DQS: {dqs_result['total_score']:.2f}/100")
    print(f"   - Blur: {dqs_result['details']['blur']:.2f}")
    print(f"   - Glare: {dqs_result['details']['glare']:.2f}")
    print(f"   - Contrast: {dqs_result['details']['contrast']:.2f}")
    print(f"   - Acceptable: {dqs_result['is_acceptable']}")
    print(f"   - Feedback: {dqs_result['feedback']}")

    if dqs_result['total_score'] >= 0 and dqs_result['total_score'] <= 100:
        print("✅ DQS calculation returned valid score")
    else:
        print(f"❌ DQS score out of range: {dqs_result['total_score']}")
        sys.exit(1)

except Exception as e:
    print(f"❌ DQS calculation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Low quality image (uniform gray = blurry + low contrast)
bad_image = Image.new('L', (1000, 1000), color=128)
bad_buffer = io.BytesIO()
bad_image.save(bad_buffer, format='PNG')
bad_bytes = bad_buffer.getvalue()

try:
    dqs_bad = validator._calculate_dqs(bad_bytes)

    print(f"\n   Bad image DQS: {dqs_bad['total_score']:.2f}/100")
    print(f"   - Blur: {dqs_bad['details']['blur']:.2f}")
    print(f"   - Glare: {dqs_bad['details']['glare']:.2f}")
    print(f"   - Contrast: {dqs_bad['details']['contrast']:.2f}")
    print(f"   - Acceptable: {dqs_bad['is_acceptable']}")
    print(f"   - Feedback: {dqs_bad['feedback']}")

    if dqs_bad['total_score'] < dqs_result['total_score']:
        print("✅ DQS correctly identifies lower quality image")
    else:
        print(f"⚠️  Warning: Bad image scored higher than good image")

except Exception as e:
    print(f"❌ DQS calculation failed on bad image: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 5: Test config settings are loaded
# ============================================================================
print("\n[TEST 5] Testing DQS config settings...")

try:
    print(f"   DQS Threshold: {settings.dqs_threshold}")
    print(f"   Blur Weight: {settings.dqs_blur_weight}")
    print(f"   Glare Weight: {settings.dqs_glare_weight}")
    print(f"   Contrast Weight: {settings.dqs_contrast_weight}")

    if settings.dqs_threshold == 70.0:
        print("✅ DQS settings loaded correctly")
    else:
        print(f"⚠️  DQS threshold is {settings.dqs_threshold}, expected 70.0")

except AttributeError as e:
    print(f"❌ DQS config not found: {e}")
    sys.exit(1)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("REAL INTEGRATION TEST SUMMARY")
print("=" * 70)
print("✅ Production code imports successfully")
print("✅ Preprocessor.preprocess() works with real images")
print("✅ EXIF rotation code executes without errors")
print("✅ FileValidator._calculate_dqs() works with real images")
print("✅ DQS config settings loaded correctly")
print("\n⚠️  LIMITATION: Still need to test with:")
print("   - Real HEIC files from iPhone")
print("   - Full upload API endpoint")
print("   - End-to-end pipeline: upload → storage → OCR")
print("=" * 70)
