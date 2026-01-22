# Render Auto-Deploy Configuration
**Date**: 2026-01-22

---

## The Problem

Auto-deploy wasn't working even though it's "enabled in Render dashboard." Pushes to GitHub weren't triggering automatic deployments.

---

## Root Cause

The `render.yaml` was missing the `repo` field. Without this, Render cannot establish the GitHub repository connection for automatic deployments.

### Before (Broken):
```yaml
services:
  - type: web
    name: image-processing
    # Missing repo field!
    branch: main
    autoDeploy: true
```

### After (Fixed):
```yaml
services:
  - type: web
    name: image-processing
    repo: https://github.com/shortalex12333/Image-processing  # ← Added!
    branch: main
    autoDeploy: true
```

**Commit**: `3af9ce7` - "fix: Add repo field to render.yaml for auto-deploy"

---

## How Render Auto-Deploy Works

### Two Deployment Methods:

#### Method 1: Manual Dashboard Setup (What you probably have)
1. Service created manually in Render dashboard
2. GitHub repo connected in "Settings" → "Build & Deploy"
3. Auto-deploy toggle enabled
4. **Webhook**: Render creates a webhook in your GitHub repo settings

**How to verify**:
- Go to GitHub: https://github.com/shortalex12333/Image-processing/settings/hooks
- Should see a Render webhook URL: `https://api.render.com/deploy/...`
- Check "Recent Deliveries" to see if pushes are triggering it

#### Method 2: Infrastructure as Code (What render.yaml enables)
1. `render.yaml` in repo defines the service
2. Deploy using: "New" → "Blueprint" in Render dashboard
3. Render reads `render.yaml` and creates/updates service
4. Auto-deploy configured via `autoDeploy: true` in yaml

**We're using**: Hybrid (manual service + render.yaml config)

---

## Verification Checklist

### ✅ In This Repository (Code Side):

- [x] `render.yaml` exists
- [x] `repo` field set to GitHub URL
- [x] `branch: main` matches your git branch
- [x] `autoDeploy: true` is set
- [x] `Dockerfile` exists and builds successfully

### ⚠️ In Render Dashboard (Your Side):

Check these in Render dashboard at:
https://dashboard.render.com/web/srv-d5gou9qdbo4c73dg61u0

1. **Settings → Build & Deploy → Auto-Deploy**
   - [ ] Auto-Deploy is **ON**
   - [ ] Branch is set to: `main`

2. **Settings → Build & Deploy → GitHub Connection**
   - [ ] Repository: `shortalex12333/Image-processing`
   - [ ] Status: Connected ✓

3. **Events Tab**
   - [ ] Shows deployment events when you push to GitHub
   - [ ] If empty: webhook not working

### ⚠️ In GitHub Repository (Your Side):

Check at: https://github.com/shortalex12333/Image-processing/settings/hooks

1. **Webhooks**
   - [ ] Render webhook exists
   - [ ] Webhook URL: `https://api.render.com/deploy/srv-...`
   - [ ] Recent Deliveries shows successful requests
   - [ ] If webhook missing: Render connection broken

---

## If Auto-Deploy Still Doesn't Work

### Problem: No Webhook in GitHub

**Cause**: Render service not properly connected to GitHub repo

**Fix**:
1. In Render Dashboard → Settings → Build & Deploy
2. Disconnect GitHub repo
3. Reconnect GitHub repo
4. This recreates the webhook

### Problem: Webhook Exists But Failing

**Cause**: Webhook deliveries show errors

**Fix**:
1. Go to GitHub → Settings → Webhooks → Render webhook
2. Click "Recent Deliveries"
3. Check error messages
4. Common issues:
   - Authentication failed → Reconnect in Render
   - Invalid payload → render.yaml syntax error

### Problem: Deployments Not Triggering

**Cause**: Branch mismatch

**Fix**:
1. In Render Dashboard → Settings → Build & Deploy
2. Change "Branch" to match your git branch: `main`
3. Verify render.yaml also says `branch: main`

---

## Testing Auto-Deploy

### Test 1: Make a Simple Change

```bash
# Make a trivial change
echo "# Test auto-deploy" >> README.md

# Commit and push
git add README.md
git commit -m "test: Verify auto-deploy works"
git push origin main

# Check Render dashboard "Events" tab
# Should see new deployment start within 30 seconds
```

### Test 2: Check Webhook Manually

```bash
# Get the webhook URL from GitHub settings
# Send a test payload

curl -X POST https://api.render.com/deploy/srv-YOUR-ID \
  -H "Content-Type: application/json" \
  -d '{"ref": "refs/heads/main"}'

# Should trigger deployment in Render
```

---

## Expected Behavior (When Working)

### After `git push origin main`:

**Within 30 seconds**:
1. GitHub sends webhook to Render
2. Render receives push notification
3. Render queues new build

**Render Dashboard → Events**:
```
[Now] Build queued - Commit 3af9ce7
      ↓
[+30s] Build started - Installing dependencies
      ↓
[+5m] Build complete - Pushing to registry
      ↓
[+6m] Deploy started - Starting new container
      ↓
[+7m] Deploy live ✅
```

**No manual action needed!**

---

## Current Status

### What I Fixed:

✅ Added `repo` field to render.yaml (commit 3af9ce7)
✅ Ensured `autoDeploy: true` is set
✅ Verified `branch: main` matches git branch

### What You Need to Verify:

1. **Render Dashboard**:
   - Auto-Deploy is enabled
   - GitHub repo is connected
   - Branch is set to `main`

2. **GitHub Settings**:
   - Render webhook exists
   - Recent deliveries are successful

3. **Test**:
   - Make a commit and push
   - Check if deployment auto-triggers in Render Events tab

---

## Alternative: Force Render to Use render.yaml

If you want Render to FULLY manage deployment from the render.yaml file:

### Option A: Redeploy as Blueprint

1. In Render Dashboard → "New" → "Blueprint"
2. Connect to: `https://github.com/shortalex12333/Image-processing`
3. Render reads `render.yaml` and creates service
4. Old manual service can be deleted

**Pros**:
- Infrastructure as Code (IaC)
- render.yaml is source of truth
- Easy to recreate service

**Cons**:
- Need to reconfigure environment variables
- Slight downtime during transition

### Option B: Keep Current Setup (Recommended)

1. Keep manually created service
2. Use render.yaml for documentation only
3. Ensure GitHub webhook is working
4. Auto-deploy happens via webhook, not render.yaml

**This is simpler and avoids downtime.**

---

## Debugging Commands

### Check if webhook is registered:

```bash
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/shortalex12333/Image-processing/hooks

# Look for webhook with:
# - "url": "https://api.render.com/deploy/..."
# - "active": true
```

### Check recent git commits:

```bash
git log --oneline -5

# Verify commits are being pushed:
git log origin/main --oneline -5
```

### Verify Render can access repo:

In Render Dashboard:
1. Settings → Build & Deploy
2. Click "Manual Deploy" → "Deploy latest commit"
3. If this works, connection is OK
4. Auto-deploy issue is webhook-related

---

## Summary

### The Fix:

Added `repo: https://github.com/shortalex12333/Image-processing` to render.yaml

### Next Steps:

1. **Verify webhook exists** in GitHub repo settings
2. **Test auto-deploy** by pushing a commit
3. **Check Render Events tab** to see if deployment triggers

If webhook is missing or failing, reconnect the GitHub repository in Render dashboard.

---

## Quick Reference

**GitHub Webhook URL**: Check at
https://github.com/shortalex12333/Image-processing/settings/hooks

**Render Dashboard**: Check at
https://dashboard.render.com/web/srv-d5gou9qdbo4c73dg61u0

**Expected Flow**:
```
Push to main → GitHub webhook → Render builds → Render deploys
```

**If broken**:
- No webhook → Reconnect repo in Render
- Webhook fails → Check "Recent Deliveries" for errors
- Branch mismatch → Set branch to `main` in Render

---

**Current Commit**: `3af9ce7` - render.yaml repo field added
**Ready to test**: Push any commit and watch Render Events tab
