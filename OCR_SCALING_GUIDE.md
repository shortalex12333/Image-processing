# OCR Engine Scaling Guide
## Toggle OCR Engines Based on Your Infrastructure

---

## Quick Reference

| Render Plan | RAM | Monthly Cost | Enable These Engines |
|-------------|-----|--------------|---------------------|
| **Starter** | 512 MB | $7 | `enable_google_vision=true` OR `enable_tesseract=true` |
| **Standard** | 2 GB | $25 | `enable_paddleocr=true` |
| **Pro** | 4+ GB | $85+ | `enable_surya=true` OR `enable_paddleocr=true` |

---

## MVP Phase (Current: Starter Plan - 512 MB RAM)

### Option A: Google Vision (Recommended for MVP)

**Environment Variables (Render Dashboard)**:
```bash
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=false
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false

GOOGLE_VISION_API_KEY=AIzaSyC7AeMY-xrcGzUHGAZp625Z6Qluxbx9YpQ
```

**Characteristics**:
- ✅ 80% accuracy (good enough for MVP)
- ✅ 400ms processing time (very fast)
- ✅ Only ~50 MB RAM (fits in Starter plan)
- ✅ No deployment issues
- 💰 $1.50 per 1000 images

**When to use**: You want reliable accuracy, fast processing, and minimal infrastructure cost.

---

### Option B: Tesseract (Free but Low Accuracy)

**Environment Variables (Render Dashboard)**:
```bash
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false
```

**Characteristics**:
- ❌ 31% accuracy (very poor)
- ✅ 1s processing time
- ✅ Only ~50 MB RAM (fits in Starter plan)
- ✅ 100% free
- ⚠️ Will miss most line items

**When to use**: Just testing infrastructure, not worried about accuracy yet.

---

## Growth Phase (Standard Plan - 2 GB RAM)

### Option: PaddleOCR (Best Accuracy, Free)

**Environment Variables (Render Dashboard)**:
```bash
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true          # Keep as fallback
ENABLE_PADDLEOCR=true
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false
```

**Characteristics**:
- ✅ 94% accuracy (best for packing slips!)
- ✅ Free (no API costs)
- ⏱️ 9s processing time (slower)
- 💾 ~500 MB RAM (needs Standard plan minimum)

**When to use**: You've validated the product and want best accuracy without ongoing API costs.

**Cost Comparison**:
- Upgrade to Standard: +$18/month ($25 vs $7)
- Save on Google Vision: -$1.50 per 1000 images
- Break-even: ~12,000 images/month

---

## Scale Phase (Pro Plan - 4+ GB RAM)

### Option: Surya (Highest Accuracy)

**Environment Variables (Render Dashboard)**:
```bash
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true          # Keep as fallback
ENABLE_PADDLEOCR=false
ENABLE_SURYA=true
ENABLE_AWS_TEXTRACT=false
```

**Characteristics**:
- ✅ 91% accuracy (very high)
- ✅ Free (no API costs)
- ❌ 30s processing time (very slow)
- 💾 ~4 GB RAM (needs Pro plan minimum)

**When to use**: You have complex documents that PaddleOCR struggles with, and processing time doesn't matter.

---

## How the System Works

### Auto-Selection Logic

The OCR factory automatically picks the **best enabled engine**:

```
Priority order (best to worst):
1. PaddleOCR  (enable_paddleocr=true)   → 94% accuracy, needs 2GB RAM
2. Surya      (enable_surya=true)       → 91% accuracy, needs 4GB RAM
3. Google     (enable_google_vision=true) → 80% accuracy, costs money
4. Tesseract  (enable_tesseract=true)   → 31% accuracy, last resort
```

**Example**: If you enable both `enable_paddleocr=true` and `enable_tesseract=true`:
- System will use PaddleOCR (higher priority)
- If PaddleOCR fails or crashes, falls back to Tesseract

---

## Configuration for Each Tier

### Starter Plan (512 MB) - Current Setup

**Add these to Render Environment Variables:**

```bash
# OCR Engine Flags
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false

# API Key (required for Google Vision)
GOOGLE_VISION_API_KEY=AIzaSyC7AeMY-xrcGzUHGAZp625Z6Qluxbx9YpQ
```

**Result**: Uses Google Vision with Tesseract fallback

---

### Standard Plan (2 GB) - When You Upgrade

**Update these in Render:**

```bash
# OCR Engine Flags
ENABLE_GOOGLE_VISION=false     # ← Disable to save API costs
ENABLE_TESSERACT=true          # ← Keep as fallback
ENABLE_PADDLEOCR=true          # ← Enable! You have enough RAM now
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false
```

**Result**: Uses PaddleOCR (94% accuracy, free), Tesseract fallback

---

### Pro Plan (4+ GB) - If You Need Maximum Accuracy

**Update these in Render:**

```bash
# OCR Engine Flags
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true          # ← Keep as fallback
ENABLE_PADDLEOCR=true          # ← Primary choice
ENABLE_SURYA=true              # ← Available if needed
ENABLE_AWS_TEXTRACT=false
```

**Result**: Uses PaddleOCR first, can manually switch to Surya for tough documents

---

## Immediate Action (For Current Deployment)

**To fix the 502 errors you're seeing:**

1. **Go to Render Dashboard** → Environment Variables
2. **Add these variables:**

```bash
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false
GOOGLE_VISION_API_KEY=AIzaSyC7AeMY-xrcGzUHGAZp625Z6Qluxbx9YpQ
```

3. **Click "Save Changes"** → Auto-deploy will trigger
4. **Wait 5 minutes** → Service should be stable
5. **Test authentication** → Should work now!

---

## Cost Breakdown by Tier

### Starter + Google Vision (Current Recommendation)

**Fixed Costs**:
- Render Starter: $7/month

**Variable Costs**:
- Google Vision: $1.50 per 1000 images
- Example: 5,000 images/month = $7.50/month in API costs
- **Total**: $14.50/month

---

### Standard + PaddleOCR (After Product Validation)

**Fixed Costs**:
- Render Standard: $25/month

**Variable Costs**:
- None (PaddleOCR is free)
- **Total**: $25/month (flat)

**Break-even**: ~12,000 images/month compared to Starter + Google Vision

---

## How to Switch Engines

### During Development (No Code Changes)

Just update environment variables in Render:

1. Go to Render Dashboard
2. Click "Environment" tab
3. Change the `ENABLE_*` flags
4. Save → Auto-deploy happens
5. New engine is active in 5 minutes

### No Downtime Required

The factory pattern means:
- No code changes needed
- No git commits required
- Just flip environment variables
- System picks best available engine automatically

---

## Troubleshooting

### Error: "No OCR engines available"

**Cause**: All engines are disabled (`ENABLE_*=false`)

**Fix**: Enable at least one engine (recommend `ENABLE_TESSERACT=true` as minimum)

### Error: "GOOGLE_VISION_API_KEY not configured"

**Cause**: `ENABLE_GOOGLE_VISION=true` but no API key set

**Fix**: Add `GOOGLE_VISION_API_KEY` to Render environment variables

### 502 Errors / Service Crashes

**Cause**: Enabled an engine that needs more RAM than your plan provides

**Fix**: Check the table at top - disable heavy engines (PaddleOCR, Surya) on Starter plan

---

## Summary

✅ **For MVP (Now)**:
- Starter plan + Google Vision
- Toggle: `ENABLE_GOOGLE_VISION=true`
- Cost: $7/month + $1.50/1000 images

✅ **For Growth (Later)**:
- Standard plan + PaddleOCR
- Toggle: `ENABLE_PADDLEOCR=true`
- Cost: $25/month flat

✅ **For Scale (Future)**:
- Pro plan + PaddleOCR/Surya
- Toggle: `ENABLE_SURYA=true`
- Cost: $85/month+ flat

**Just flip switches in Render as you grow. No code changes needed!**
