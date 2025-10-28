# Second Brain Diagnosis Report

## Issue Identified: Missing Screen Recording Permission ❌

### Root Cause
The `screencapture` command is failing with error: **"could not create image from display"**

This means macOS has **not granted Screen Recording permission** to the Terminal or Python process running Second Brain.

### Current Status
- ✅ Service is running (PID: 41696, started at 3:29 PM)
- ✅ Python 3.11.12 environment active
- ✅ Package installed correctly
- ✅ OpenAI API key configured
- ✅ Database initialized
- ✅ All dependencies present
- ❌ **Screen Recording permission NOT granted**
- ❌ No screenshots captured (0 frames in database)

### Why This Happens
macOS requires explicit user permission for any app to capture screen content. Without this permission, the `screencapture` command silently fails.

## Solution: Grant Screen Recording Permission

### Step 1: Stop the Current Service
```bash
cd /Users/gregcmartin/Desktop/Second\ Brain
source venv/bin/activate
second-brain stop
```

### Step 2: Grant Screen Recording Permission

1. Open **System Settings** (or System Preferences on older macOS)
2. Navigate to **Privacy & Security** → **Screen Recording**
3. Look for one of these in the list:
   - **Terminal** (if you're running from Terminal)
   - **iTerm** (if you're using iTerm2)
   - **Visual Studio Code** (if running from VS Code terminal)
   - **Python** (the Python interpreter)

4. **Enable the checkbox** next to the application
5. You may need to **quit and restart** the Terminal/application for changes to take effect

### Step 3: Restart Terminal/Application
- Completely quit your Terminal or VS Code
- Reopen it
- Navigate back to the project directory

### Step 4: Test Screen Capture
```bash
cd /Users/gregcmartin/Desktop/Second\ Brain
source venv/bin/activate

# Test if screencapture works now
screencapture -x /tmp/test_screenshot.png && ls -lh /tmp/test_screenshot.png
```

If this succeeds and shows a file size (e.g., "1.2M"), permission is granted! ✅

### Step 5: Restart Second Brain
```bash
second-brain start
```

### Step 6: Verify Capture is Working
Wait 30-60 seconds, then check:
```bash
second-brain status
```

You should see:
- Total Frames: > 0 (increasing)
- Text Blocks: > 0 (after OCR processes)

## Alternative: Run with Accessibility Permissions

If Screen Recording permission doesn't work, you may also need:

1. **System Settings** → **Privacy & Security** → **Accessibility**
2. Add your Terminal/Python to the list
3. Enable the checkbox

## Verification Commands

After granting permissions and restarting:

```bash
# Check if frames are being captured
ls -la ~/Library/Application\ Support/second-brain/frames/2025/

# Check database stats
second-brain status

# View recent activity
second-brain query "test" --limit 5
```

## Expected Behavior After Fix

Once permissions are granted:
- Screenshots captured every 1 second (default FPS)
- Files appear in: `~/Library/Application Support/second-brain/frames/YYYY/MM/DD/`
- Each frame has: `.png` (screenshot) + `.json` (metadata)
- OCR processes frames in batches
- Text blocks stored in database
- Search becomes functional

## Additional Notes

### Why the Service Appeared to be "Running"
The Python process was running successfully, but the `screencapture` command was failing silently due to permission denial. The service didn't crash because it's designed to handle capture failures gracefully.

### Logs Location
Currently no log files are being written. Once capture starts working, logs will appear in:
```
~/Library/Application Support/second-brain/logs/
```

### Performance Expectations
- CPU: ~5% during capture
- Memory: ~500MB
- Disk: ~1-2GB per day
- API Cost: ~$0.01-0.05 per day (GPT-5 Vision)

## Need Help?

If you continue to have issues after granting permissions:
1. Check Console.app for system-level errors
2. Try running with `sudo` (not recommended for production)
3. Verify Terminal has Full Disk Access (Privacy & Security → Full Disk Access)
