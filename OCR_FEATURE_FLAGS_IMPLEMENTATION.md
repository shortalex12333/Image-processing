# OCR Feature Flags Implementation
## Scale OCR Engines as You Grow - Just Flip Switches

**Date**: 2026-01-22
**Status**: ✅ Implemented

---

## What Was Built

A **feature flag system** for OCR engines that lets you toggle engines on/off based on your infrastructure tier.

### Key Benefits:

1. **No code changes needed** - Just update environment variables
2. **Auto-selects best engine** - System picks the best available enabled engine
3. **Scales with your plan** - Enable better engines as you upgrade Render plans
4. **Clear separation** - Each tier has its own recommended configuration

---

## Files Modified

### 1. `src/config.py`
Added feature flags for each OCR engine:
```python
# TIER 1: Starter Plan (512 MB RAM)
enable_google_vision: bool = False
enable_tesseract: bool = True

# TIER 2: Standard Plan (2 GB RAM)
enable_paddleocr: bool = False

# TIER 3: Pro Plan (4+ GB RAM)
enable_surya: bool = False
enable_aws_textract: bool = False
```

### 2. `src/ocr/ocr_factory.py`
Updated to auto-select best available engine:
```python
def _select_best_available_engine(cls) -> BaseOCR:
    """Try engines in priority order: PaddleOCR → Surya → Google → Tesseract"""
    engines_to_try = [
        ("paddleocr", settings.enable_paddleocr, cls._create_paddleocr),
        ("surya", settings.enable_surya, cls._create_surya),
        ("google_vision", settings.enable_google_vision, cls._create_google_vision),
        ("tesseract", settings.enable_tesseract, cls._create_tesseract),
    ]
    # Returns first enabled engine that initializes successfully
```

### 3. `render.yaml`
Added environment variable definitions:
```yaml
envVars:
  - key: ENABLE_GOOGLE_VISION
    sync: false
  - key: ENABLE_TESSERACT
    value: true
  - key: ENABLE_PADDLEOCR
    value: false
  # ... etc
```

### 4. `.env.example`
Updated with clear tier-based configuration guide

### 5. `OCR_SCALING_GUIDE.md` (NEW)
Complete guide for configuring OCR engines by plan tier

---

## How It Works

### Auto-Selection Logic

The factory checks enabled flags in **priority order** (best to worst):

```
1. PaddleOCR  → 94% accuracy, free, needs 2GB RAM
2. Surya      → 91% accuracy, free, needs 4GB RAM
3. Google     → 80% accuracy, costs $1.50/1000, needs 512MB RAM
4. Tesseract  → 31% accuracy, free, needs 512MB RAM
```

### Example Scenarios

**Scenario 1: Starter Plan (Current)**
```bash
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
```
→ Uses Google Vision (best enabled engine)

**Scenario 2: After Upgrading to Standard Plan**
```bash
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=true  # ← Now have enough RAM!
```
→ Uses PaddleOCR (better accuracy, no API costs)

**Scenario 3: All Disabled Except Tesseract**
```bash
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
```
→ Uses Tesseract (only option available)

---

## Immediate Action Required (Fix Current 502 Errors)

### Problem
Your service is crashing with 502 errors because PaddleOCR is trying to load but you only have 512 MB RAM.

### Solution
Add these environment variables in Render **right now**:

```bash
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false

GOOGLE_VISION_API_KEY=AIzaSyC7AeMY-xrcGzUHGAZp625Z6Qluxbx9YpQ
```

### Steps:
1. Go to Render Dashboard → Environment tab
2. Add the 6 variables above
3. Click "Save" → Auto-deploy triggers
4. Wait 5 minutes
5. Test → Should work!

---

## Migration Path (As You Scale)

### Phase 1: MVP (Now)
**Plan**: Starter (512 MB, $7/month)
**Config**: Google Vision enabled
**Cost**: $7/month + $1.50/1000 images
**Accuracy**: 80%

### Phase 2: Growth (When You Have Customers)
**Plan**: Standard (2 GB, $25/month)
**Config**: PaddleOCR enabled
**Cost**: $25/month (flat)
**Accuracy**: 94%
**Break-even**: 12,000 images/month

### Phase 3: Scale (High Volume)
**Plan**: Pro (4+ GB, $85/month)
**Config**: PaddleOCR + Surya enabled
**Cost**: $85/month (flat)
**Accuracy**: 94% (PaddleOCR) or 91% (Surya for tough docs)

---

## Configuration By Tier

### Starter Plan (512 MB) - Current

**Render Environment Variables:**
```bash
# Enable lightweight engines only
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false

# Required API key
GOOGLE_VISION_API_KEY=your-key-here
```

**Result**:
- Uses Google Vision (80% accuracy, fast, costs money)
- Falls back to Tesseract if Google fails

---

### Standard Plan (2 GB) - After Upgrade

**Render Environment Variables:**
```bash
# Enable PaddleOCR (best for packing slips)
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=true
ENABLE_SURYA=false
```

**Result**:
- Uses PaddleOCR (94% accuracy, free, slower)
- Falls back to Tesseract if PaddleOCR fails
- No API costs!

---

### Pro Plan (4+ GB) - Future

**Render Environment Variables:**
```bash
# Enable everything for maximum flexibility
ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=true
ENABLE_SURYA=true
```

**Result**:
- Uses PaddleOCR by default (best all-around)
- Surya available for very complex documents
- Tesseract as last resort fallback

---

## Code Changes Summary

### Before (Hardcoded Engine)
```python
# config.py
ocr_engine: Literal["paddleocr", "tesseract", ...] = "paddleocr"

# ocr_factory.py
engine_name = settings.ocr_engine.lower()
if engine_name == "paddleocr":
    cls._instance = cls._create_paddleocr()
```
**Problem**: Always tries to load PaddleOCR → crashes on 512 MB plan

---

### After (Feature Flags)
```python
# config.py
enable_google_vision: bool = False
enable_tesseract: bool = True
enable_paddleocr: bool = False
enable_surya: bool = False

# ocr_factory.py
def _select_best_available_engine(cls):
    for engine_name, is_enabled, create_func in priority_order:
        if is_enabled:
            return create_func()  # Use first enabled engine
```
**Solution**: Only loads enabled engines → no crashes

---

## Testing

### Verify Feature Flags Work

1. **Set Tesseract only**:
   ```bash
   ENABLE_TESSERACT=true
   ENABLE_GOOGLE_VISION=false
   ENABLE_PADDLEOCR=false
   ```
   → Should use Tesseract

2. **Set Google Vision**:
   ```bash
   ENABLE_TESSERACT=true
   ENABLE_GOOGLE_VISION=true
   ENABLE_PADDLEOCR=false
   GOOGLE_VISION_API_KEY=your-key
   ```
   → Should use Google Vision (higher priority than Tesseract)

3. **Enable PaddleOCR** (after upgrading to 2GB plan):
   ```bash
   ENABLE_PADDLEOCR=true
   ```
   → Should use PaddleOCR (highest priority)

---

## Backward Compatibility

### Old Config Still Works
```bash
OCR_ENGINE=tesseract
```
**Note**: This is deprecated but still functional. System will ignore feature flags if `OCR_ENGINE` is explicitly set.

### New Config (Recommended)
```bash
ENABLE_TESSERACT=true
ENABLE_GOOGLE_VISION=false
```
System auto-selects best available engine.

---

## Troubleshooting

### Error: "No OCR engines available"
**Cause**: All flags are `false`
**Fix**: Enable at least one: `ENABLE_TESSERACT=true`

### Service Crashes with 502
**Cause**: Heavy engine enabled on small plan (e.g., `ENABLE_PADDLEOCR=true` on 512 MB)
**Fix**: Disable heavy engines, enable lightweight ones

### Error: "GOOGLE_VISION_API_KEY not configured"
**Cause**: `ENABLE_GOOGLE_VISION=true` but no API key
**Fix**: Add `GOOGLE_VISION_API_KEY` environment variable

---

## Next Steps

### 1. Immediate (Fix 502 Errors)
- Add feature flag environment variables to Render
- Set `ENABLE_GOOGLE_VISION=true`
- Add Google Vision API key
- Verify deployment succeeds

### 2. Test Authentication (After Service Stable)
- Verify Supabase client auth works
- Test file upload with real JWT
- Confirm OCR processing completes

### 3. Monitor Costs (First Month)
- Track image processing volume
- Calculate Google Vision API costs
- Determine if/when to upgrade to Standard plan

### 4. Plan Upgrade (When Ready)
- Upgrade to Standard plan (2 GB RAM)
- Change `ENABLE_PADDLEOCR=true`
- Enjoy 94% accuracy with no API costs

---

## Summary

✅ **Built**: Feature flag system for OCR engines
✅ **Benefit**: Scale engines by just updating environment variables
✅ **No Code Changes**: Toggle flags in Render dashboard
✅ **Clear Path**: Starter → Standard → Pro plans well-defined

**Next**: Add feature flags to Render to fix current 502 errors!

See: **OCR_SCALING_GUIDE.md** for complete configuration guide.
