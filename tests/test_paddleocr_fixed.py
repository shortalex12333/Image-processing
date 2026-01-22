"""
Test PaddleOCR on real packing slips (fixed parameters)
"""

import sys
import os
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

TEST_FILES = [
    "/Users/celeste7/Downloads/fake invoices/7.png",
    "/Users/celeste7/Downloads/fake invoices/5.png",
    "/Users/celeste7/Downloads/fake invoices/1.jpg",
]

def test_paddleocr():
    """Test PaddleOCR on real files"""
    print("="*60)
    print("PADDLEOCR - Real Packing Slip Test (Fixed)")
    print("="*60)

    try:
        from paddleocr import PaddleOCR

        # Fixed: remove show_log parameter, use correct parameter name
        ocr = PaddleOCR(use_textline_orientation=True, lang='en')

        results = []
        for file_path in TEST_FILES:
            if not os.path.exists(file_path):
                print(f"⚠️  File not found: {file_path}")
                continue

            start = time.time()
            result = ocr.predict(file_path)
            processing_time = (time.time() - start) * 1000

            if not result or not result[0]:
                print(f"\nFile: {Path(file_path).name}")
                print(f"  No text detected")
                continue

            # Extract text and confidence from new API format
            page_result = result[0]
            text_lines = page_result.get('rec_texts', [])
            confidences = page_result.get('rec_scores', [])

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
            avg_time = sum(r["time_ms"] for r in results) / len(results)
            print(f"\n{'='*60}")
            print(f"PADDLEOCR AVERAGE CONFIDENCE: {avg_conf:.1%}")
            print(f"PADDLEOCR AVERAGE TIME: {avg_time:.0f}ms")
            print(f"{'='*60}")
            return avg_conf
        else:
            print("No results")
            return 0

    except ImportError:
        print("⚠️  PaddleOCR not installed. Run: pip3 install paddleocr")
        return 0
    except Exception as e:
        print(f"✗ PaddleOCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    test_paddleocr()
