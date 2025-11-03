#!/bin/bash
# WSL Terminal Reset Script
# Fixes terminal spawning issues after Ubuntu 22.04 -> 24.04 upgrade
# Run once: bash scripts/wsl-reset-terminals.sh

set -e

echo "🔧 WSL Terminal Reset"
echo "===================="

# 1. Backup current bashrc
if [ -f ~/.bashrc ]; then
    cp ~/.bashrc ~/.bashrc.backup
    echo "✅ Backed up ~/.bashrc to ~/.bashrc.backup"
fi

# 2. Remove problematic bash initialization
# Remove any lines that might cause re-initialization loops
if grep -q "exec bash" ~/.bashrc 2>/dev/null || \
   grep -q "source ~/.bashrc" ~/.bashrc 2>/dev/null; then
    echo "⚠️  Found recursive bashrc source - cleaning up..."
    grep -v "exec bash" ~/.bashrc | grep -v "source ~/.bashrc" > ~/.bashrc.tmp
    mv ~/.bashrc.tmp ~/.bashrc
fi

# 3. Create clean minimal bashrc if needed
if [ ! -s ~/.bashrc ] || [ $(wc -l < ~/.bashrc) -lt 5 ]; then
    echo "📝 Creating minimal ~/.bashrc..."
    cat > ~/.bashrc << 'EOF'
# Minimal .bashrc for WSL
export PATH="/home/linuxbrew/.linuxbrew/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# Bash options
set +H  # Disable history expansion if it causes issues

# Simple prompt
PS1='\u@\h:\w\$ '

# Aliases
alias ll='ls -l'
alias la='ls -la'
EOF
    echo "✅ Created clean ~/.bashrc"
fi

# 4. Check for systemd conflicts in WSL
if [ -f /etc/wsl.conf ]; then
    echo "📋 Current /etc/wsl.conf:"
    cat /etc/wsl.conf
    if grep -q "systemd=true" /etc/wsl.conf; then
        echo "⚠️  systemd is enabled - this can cause terminal issues"
        echo "   Consider setting systemd=false in /etc/wsl.conf (requires sudo)"
    fi
else
    echo "ℹ️  No /etc/wsl.conf found (using defaults)"
fi

# 5. Verify uv PATH
if command -v uv &> /dev/null; then
    echo "✅ uv found at: $(which uv)"
else
    echo "⚠️  uv not found - ensure it's installed and in PATH"
    echo "   Try: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# 6. Verify Python
if command -v python3 &> /dev/null; then
    echo "✅ Python $(python3 --version) found at: $(which python3)"
else
    echo "⚠️  Python not found"
fi

echo ""
echo "✅ WSL terminal cleanup complete!"
echo ""
echo "Next steps:"
echo "1. Restart VS Code completely (close all windows)"
echo "2. Reopen the workspace"
echo "3. Open integrated terminal (Ctrl+\`)"
echo "4. You should see only ONE terminal tab (not 15-20)"
echo ""
echo "If issues persist:"
echo "  - Check: wsl --shutdown"
echo "  - Then: Restart WSL via PowerShell: 'wsl --terminate Ubuntu'"
