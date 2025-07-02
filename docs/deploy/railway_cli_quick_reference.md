# Railway CLI Quick Reference

## Common Commands (No Hanging)

### **Quick Status Checks:**
```bash
railway status                    # Project info
railway whoami                   # Current user
railway variables | head -10     # Environment variables (first 10)
```

### **Log Viewing (Non-Streaming):**
```bash
# Get recent logs without streaming
railway logs --deployment | head -50    # Last 50 deployment logs
railway logs --build | head -20         # Build logs
railway logs --json | head -10          # JSON format logs

# Search logs for specific patterns
railway logs --deployment | grep -i "error" | tail -10    # Recent errors
railway logs --deployment | grep "BOOT" | tail -5         # Boot messages
```

### **Deployment Management:**
```bash
railway redeploy              # Restart/redeploy service
railway up                    # Deploy current directory
railway open                  # Open Railway dashboard
```

### **Environment Variables:**
```bash
railway variables             # Show all variables
railway variables | grep -i "helius"    # Find specific variables
```

## Commands That WILL Stream (Use Ctrl+C to stop):
```bash
railway logs                  # ⚠️ STREAMS CONTINUOUSLY - Press Ctrl+C to stop
railway logs --deployment    # ⚠️ STREAMS CONTINUOUSLY - Press Ctrl+C to stop
```

## Pro Tips:

### **Save Logs to File:**
```bash
# Collect logs for 5 seconds then save
railway logs --deployment > tmp/logs.txt &
LOGS_PID=$!
sleep 5
kill $LOGS_PID 2>/dev/null
echo "Logs saved to tmp/logs.txt"
```

### **Quick Error Check:**
```bash
railway logs --deployment | grep -i "error" | tail -5
```

### **Check Recent Startup:**
```bash
railway logs --deployment | grep -E "(Starting|BOOT)" | tail -10
```

## Updated get_railway_logs.sh Script:
Your `scripts/get_railway_logs.sh` has been updated to avoid hanging and works properly now.

---
**Remember:** `railway logs` without parameters streams continuously. Always use `| head -N` or `--deployment | head -N` for quick checks. 