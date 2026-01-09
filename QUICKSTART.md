# Quick Start Guide
## Get Image Processing Service Running in 5 Minutes

---

## Prerequisites

- Python 3.11+ installed
- Tesseract OCR installed:
  - macOS: `brew install tesseract`
  - Ubuntu: `sudo apt-get install tesseract-ocr`
  - Windows: Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
- Supabase project with credentials
- OpenAI API key

---

## Step 1: Setup Environment

```bash
cd /private/tmp/Image-processing

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Step 2: Configure Environment Variables

```bash
# Copy template
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your favorite editor
```

**Required variables:**
```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key
OPENAI_API_KEY=sk-your-key-here
JWT_SECRET=your-jwt-secret  # Match your main PMS app
```

**Optional (use defaults):**
```bash
OCR_ENGINE=tesseract
MAX_UPLOADS_PER_HOUR=50
MAX_FILE_SIZE_MB=15
ENVIRONMENT=development
LOG_LEVEL=info
```

---

## Step 3: Verify Tesseract Installation

```bash
tesseract --version
# Should output: tesseract 5.x.x

# If not found, update TESSERACT_CMD in .env
# macOS: /usr/local/bin/tesseract
# Linux: /usr/bin/tesseract
# Windows: C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## Step 4: Run the Application

```bash
# Option 1: Direct Python
python -m src.main

# Option 2: Uvicorn (recommended for development)
uvicorn src.main:app --reload --port 8001 --log-level info

# Option 3: Docker
docker build -t image-processing .
docker run -p 8001:8001 --env-file .env image-processing
```

---

## Step 5: Verify It's Running

**Open browser:**
```
http://localhost:8001
```

**Check health:**
```bash
curl http://localhost:8001/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development"
}
```

**View API docs:**
```
http://localhost:8001/docs  (Swagger UI)
http://localhost:8001/redoc (ReDoc)
```

---

## Step 6: Test Individual Components

### Test File Validation

```python
# Create test script: test_validation.py
from src.intake.validator import FileValidator
import asyncio

async def test():
    validator = FileValidator("receiving")
    # You'll need to provide a real UploadFile object
    # For now, verify the class loads correctly
    print("✅ FileValidator loaded successfully")

asyncio.run(test())
```

### Test OCR (with sample image)

```python
# test_ocr.py
from src.ocr.tesseract_ocr import TesseractOCR
from PIL import Image
import io
import asyncio

async def test():
    # Create a simple test image with text
    img = Image.new('RGB', (400, 100), color='white')
    # In reality, you'd load a real image here

    ocr = TesseractOCR()
    print("✅ TesseractOCR initialized successfully")

    # To actually test OCR:
    # image_bytes = open('sample_packing_slip.jpg', 'rb').read()
    # result = await ocr.extract_text(image_bytes)
    # print(result)

asyncio.run(test())
```

### Test Row Parser

```python
# test_parser.py
from src.extraction.row_parser import RowParser

# Sample OCR text
ocr_text = """
12 ea MTU Oil Filter MTU-OF-4568
5 box Air Filter Elements MTU-AF-4567
24 pcs Spark Plugs NGK-7890
"""

parser = RowParser()
result = parser.parse_lines(ocr_text)

print(f"Lines extracted: {len(result['lines'])}")
print(f"Coverage: {result['coverage']:.2%}")

for line in result['lines']:
    print(f"  {line['quantity']} {line['unit']} - {line['description']}")
```

### Test Cost Controller

```python
# test_cost.py
from src.extraction.cost_controller import SessionCostTracker, CostController
from uuid import uuid4

session_id = uuid4()
tracker = SessionCostTracker(session_id)
controller = CostController(tracker)

# Simulate low coverage scenario
decision = controller.decide_next_action(
    coverage=0.55,  # Only 55% parsed
    table_confidence=0.7,
    llm_attempts=0
)

print(f"Action: {decision.action}")
print(f"Reason: {decision.reason}")
print(f"Model: {decision.model}")
```

---

## Common Issues & Solutions

### Issue: "tesseract: command not found"

**Solution:**
```bash
# Verify Tesseract is installed
which tesseract  # macOS/Linux
where tesseract  # Windows

# If not found, install:
brew install tesseract  # macOS
sudo apt-get install tesseract-ocr  # Ubuntu

# Update .env with correct path
TESSERACT_CMD=/usr/local/bin/tesseract
```

### Issue: "ModuleNotFoundError: No module named 'cv2'"

**Solution:**
```bash
pip install opencv-python
```

### Issue: "Invalid JWT token"

**Solution:**
- Ensure JWT_SECRET in .env matches your main PMS app
- Check JWT format in Authorization header: `Bearer <token>`
- Verify token hasn't expired

### Issue: "Supabase connection failed"

**Solution:**
- Verify NEXT_PUBLIC_SUPABASE_URL is correct
- Check SUPABASE_SERVICE_ROLE_KEY (not anon key for service role)
- Ensure network access to Supabase (not blocked by firewall)
- Test connection:
```python
from src.database import get_supabase_service
client = get_supabase_service()
print(client)  # Should not error
```

### Issue: "OpenAI API error"

**Solution:**
- Verify OPENAI_API_KEY is valid (starts with `sk-`)
- Check API key has credits/quota remaining
- Ensure gpt-4.1-mini model is available (or update model name in .env)

---

## Testing the Full Pipeline (Manual)

**When routes are implemented**, you can test like this:

```bash
# 1. Upload image
curl -X POST http://localhost:8001/api/v1/images/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "files=@sample_packing_slip.pdf" \
  -F "upload_type=receiving"

# 2. Get session with draft lines
curl http://localhost:8001/api/v1/receiving/sessions/SESSION_ID \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 3. Verify a line
curl -X PATCH http://localhost:8001/api/v1/receiving/sessions/SESSION_ID/lines/LINE_ID/verify \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 4. Commit session (HOD only)
curl -X POST http://localhost:8001/api/v1/receiving/sessions/SESSION_ID/commit \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"commitment_notes": "Receiving complete, all items verified"}'
```

---

## Development Workflow

### 1. Make changes to code

```bash
# Edit files in src/
nano src/intake/validator.py
```

### 2. Run with auto-reload

```bash
uvicorn src.main:app --reload
# Server restarts automatically on file changes
```

### 3. Check logs

```bash
# Logs are output to stdout with structured format
# In development: pretty console output
# In production: JSON format
```

### 4. Run tests (when implemented)

```bash
pytest tests/ -v
pytest tests/test_ocr.py -v  # Single test file
pytest --cov=src --cov-report=html  # With coverage
```

---

## Deployment to Render.com

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit - Image Processing Service"
git remote add origin https://github.com/shortalex12333/Image-processing.git
git push -u origin main
```

### 2. Create Render Service

1. Go to [Render.com](https://render.com)
2. New → Web Service
3. Connect GitHub repo: `Image-processing`
4. Render detects `render.yaml` automatically
5. Add environment variables:
   - NEXT_PUBLIC_SUPABASE_URL
   - SUPABASE_SERVICE_ROLE_KEY
   - OPENAI_API_KEY
   - JWT_SECRET
   - (Others use defaults from render.yaml)
6. Click "Create Web Service"

### 3. Verify Deployment

```bash
# After deploy completes (~5 minutes)
curl https://your-service.onrender.com/health
```

**Your service is now live! 🎉**

---

## What's Next?

1. **Complete implementation** - See `IMPLEMENTATION_STATUS.md` for remaining tasks
2. **Add test fixtures** - Create sample packing slips in `fixtures/`
3. **Write tests** - See Step 13 in TODO list
4. **Implement routes** - See `src/routes/` TODO comments
5. **Test end-to-end** - Upload → OCR → Extract → Verify → Commit

---

## Resources

- **Full documentation**: `/docs` folder
- **API contracts**: `docs/04_api_contracts.md`
- **Model strategy**: `docs/05_model_strategy.md`
- **Implementation status**: `IMPLEMENTATION_STATUS.md`
- **README**: `README.md`

---

## Need Help?

**Check logs first:**
```bash
# The application logs everything with structured logging
# Look for ERROR or WARNING level messages
```

**Common questions:**
- "Where are the routes?" → Not yet implemented, see IMPLEMENTATION_STATUS.md
- "Can I upload images?" → Routes needed first (Priority 3 in status doc)
- "How do I test OCR?" → Use test scripts above
- "What's the cost?" → See `docs/05_model_strategy.md` for detailed cost breakdown

---

**Ready to build!** 🚀

Start with the test scripts above to verify each component works, then move on to implementing the remaining layers (reconciliation, commit, handlers, routes).
