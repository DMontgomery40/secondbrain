#!/bin/bash
# Reset script for Second Brain
# Clears all collected data and SQLite database for a fresh start

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Data directory
DATA_DIR="$HOME/Library/Application Support/second-brain"

echo -e "${YELLOW}Second Brain Reset Script${NC}"
echo "This will delete ALL captured data including:"
echo "  - Screenshots and frames"
echo "  - SQLite database"
echo "  - Video files"
echo "  - Embeddings"
echo "  - Logs"
echo ""
echo -e "${RED}WARNING: This action cannot be undone!${NC}"
echo ""

# Prompt for confirmation
read -p "Are you sure you want to reset? Type 'yes' to confirm: " confirmation

if [ "$confirmation" != "yes" ]; then
    echo -e "${YELLOW}Reset cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Checking if service is running...${NC}"

# Check if service is running and stop it
if second-brain status &>/dev/null; then
    echo -e "${YELLOW}Stopping Second Brain service...${NC}"
    second-brain stop
    sleep 2
fi

echo -e "${GREEN}✓${NC} Service stopped (or was not running)"
echo ""

# Remove data directories
if [ -d "$DATA_DIR" ]; then
    echo -e "${YELLOW}Removing data directory: $DATA_DIR${NC}"
    
    # Remove frames
    if [ -d "$DATA_DIR/frames" ]; then
        echo "  - Removing frames..."
        rm -rf "$DATA_DIR/frames"
    fi
    
    # Remove videos
    if [ -d "$DATA_DIR/videos" ]; then
        echo "  - Removing videos..."
        rm -rf "$DATA_DIR/videos"
    fi
    
    # Remove database
    if [ -d "$DATA_DIR/database" ]; then
        echo "  - Removing database..."
        rm -rf "$DATA_DIR/database"
    fi
    
    # Remove embeddings
    if [ -d "$DATA_DIR/embeddings" ]; then
        echo "  - Removing embeddings..."
        rm -rf "$DATA_DIR/embeddings"
    fi
    
    # Remove logs
    if [ -d "$DATA_DIR/logs" ]; then
        echo "  - Removing logs..."
        rm -rf "$DATA_DIR/logs"
    fi
    
    # Remove PID file if exists
    if [ -f "$DATA_DIR/second-brain.pid" ]; then
        echo "  - Removing PID file..."
        rm -f "$DATA_DIR/second-brain.pid"
    fi
    
    echo -e "${GREEN}✓${NC} All data removed"
else
    echo -e "${YELLOW}Data directory does not exist, nothing to remove${NC}"
fi

echo ""
echo -e "${GREEN}✓ Reset complete!${NC}"
echo ""
echo "You can now start fresh with: second-brain start"
