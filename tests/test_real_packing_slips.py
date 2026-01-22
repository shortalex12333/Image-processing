"""
REAL PACKING SLIP TESTING
Test actual files from /Users/celeste7/Downloads/fake invoices/
Compare Tesseract vs EasyOCR vs PaddleOCR
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Real test files
TEST_FILES = [
    "/Users/celeste7/Downloads/fake invoices/7.png",
    "/Users/celeste7/Downloads/fake invoices/5.png",
    "/Users/celeste7/Downloads/fake invoices/1.jpg",
]

async def test_tesseract_real():
    """Test Tesseract on REAL packing slips"""
    print("\n" + "="*60)
    print("TESSERACT - Real Packing Slip Test")
    print("="*60)

    from src.ocr.tesseract_ocr import TesseractOCR
    ocr = TesseractOCR()

    results = []
    for file_path in TEST_FILES:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            continue

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        result = await ocr.extract_text(file_bytes)

        print(f"\nFile: {Path(file_path).name}")
        print(f"  Confidence: {result.confidence:.1%}")
        print(f"  Processing Time: {result.processing_time_ms}ms")
        print(f"  Text Length: {len(result.text)} chars")
        print(f"  First 100 chars: {result.text[:100]}...")

        results.append({
            "file": Path(file_path).name,
            "confidence": result.confidence,
            "time_ms": result.processing_time_ms,
            "text_length": len(result.text),
            "text": result.text
        })

    if results:
        avg_conf = sum(r["confidence"] for r in results) / len(results)
        print(f"\n{'='*60}")
        print(f"TESSERACT AVERAGE CONFIDENCE: {avg_conf:.1%}")
        print(f"{'='*60}")

    return results

async def test_easyocr_real():
    """Test EasyOCR on REAL packing slips"""
    print("\n" + "="*60)
    print("EASYOCR - Real Packing Slip Test")
    print("="*60)

    try:
        import easyocr
        import time

        reader = easyocr.Reader(['en'], gpu=False)

        results = []
        for file_path in TEST_FILES:
            if not os.path.exists(file_path):
                print(f"⚠️  File not found: {file_path}")
                continue

            start = time.time()
            result = reader.readtext(file_path)
            processing_time = (time.time() - start) * 1000

            # Combine all detected text
            text = " ".join([detection[1] for detection in result])
            confidences = [detection[2] for detection in result]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            print(f"\nFile: {Path(file_path).name}")
            print(f"  Confidence: {avg_confidence:.1%}")
            print(f"  Processing Time: {processing_time:.0f}ms")
            print(f"  Text Length: {len(text)} chars")
            print(f"  Detections: {len(result)}")
            print(f"  First 100 chars: {text[:100]}...")

            results.append({
                "file": Path(file_path).name,
                "confidence": avg_confidence,
                "time_ms": processing_time,
                "text_length": len(text),
                "text": text
            })

        if results:
            avg_conf = sum(r["confidence"] for r in results) / len(results)
            print(f"\n{'='*60}")
            print(f"EASYOCR AVERAGE CONFIDENCE: {avg_conf:.1%}")
            print(f"{'='*60}")

        return results

    except ImportError:
        print("⚠️  EasyOCR not installed. Run: pip3 install easyocr")
        return []
    except Exception as e:
        print(f"✗ EasyOCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return []

async def test_paddleocr_real():
    """Test PaddleOCR on REAL packing slips"""
    print("\n" + "="*60)
    print("PADDLEOCR - Real Packing Slip Test")
    print("="*60)

    try:
        from paddleocr import PaddleOCR
        import time

        ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

        results = []
        for file_path in TEST_FILES:
            if not os.path.exists(file_path):
                print(f"⚠️  File not found: {file_path}")
                continue

            start = time.time()
            result = ocr.ocr(file_path, cls=True)
            processing_time = (time.time() - start) * 1000

            # Extract text and confidence
            text_lines = []
            confidences = []
            for line in result[0]:
                text_lines.append(line[1][0])
                confidences.append(line[1][1])

            text = " ".join(text_lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            print(f"\nFile: {Path(file_path).name}")
            print(f"  Confidence: {avg_confidence:.1%}")
            print(f"  Processing Time: {processing_time:.0f}ms")
            print(f"  Text Length: {len(text)} chars")
            print(f"  Lines Detected: {len(text_lines)}")
            print(f"  First 100 chars: {text[:100]}...")

            results.append({
                "file": Path(file_path).name,
                "confidence": avg_confidence,
                "time_ms": processing_time,
                "text_length": len(text),
                "text": text
            })

        if results:
            avg_conf = sum(r["confidence"] for r in results) / len(results)
            print(f"\n{'='*60}")
            print(f"PADDLEOCR AVERAGE CONFIDENCE: {avg_conf:.1%}")
            print(f"{'='*60}")

        return results

    except ImportError:
        print("⚠️  PaddleOCR not installed. Run: pip3 install paddleocr")
        return []
    except Exception as e:
        print(f"✗ PaddleOCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return []

async def compare_results():
    """Run all tests and compare results"""
    print("\n" + "╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  REAL PACKING SLIP OCR COMPARISON".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")

    tesseract_results = await test_tesseract_real()
    easyocr_results = await test_easyocr_real()
    paddleocr_results = await test_paddleocr_real()

    print("\n" + "="*60)
    print("FINAL COMPARISON")
    print("="*60)

    if tesseract_results:
        avg = sum(r["confidence"] for r in tesseract_results) / len(tesseract_results)
        print(f"Tesseract:  {avg:.1%} average confidence")

    if easyocr_results:
        avg = sum(r["confidence"] for r in easyocr_results) / len(easyocr_results)
        print(f"EasyOCR:    {avg:.1%} average confidence")

    if paddleocr_results:
        avg = sum(r["confidence"] for r in paddleocr_results) / len(paddleocr_results)
        print(f"PaddleOCR:  {avg:.1%} average confidence")

    print("="*60)

    # Determine winner
    engines = []
    if tesseract_results:
        engines.append(("Tesseract", sum(r["confidence"] for r in tesseract_results) / len(tesseract_results)))
    if easyocr_results:
        engines.append(("EasyOCR", sum(r["confidence"] for r in easyocr_results) / len(easyocr_results)))
    if paddleocr_results:
        engines.append(("PaddleOCR", sum(r["confidence"] for r in paddleocr_results) / len(paddleocr_results)))

    if engines:
        winner = max(engines, key=lambda x: x[1])
        print(f"\n🏆 WINNER: {winner[0]} ({winner[1]:.1%} confidence)")

    print("\n")

if __name__ == "__main__":
    asyncio.run(compare_results())
