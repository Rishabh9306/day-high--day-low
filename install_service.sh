#!/bin/bash
# Installation script for Nifty Trading Bot systemd service

set -e

echo "======================================================================"
echo "Installing Nifty 50 Trading Bot as a System Service"
echo "======================================================================"

# Create logs directory
echo "Creating logs directory..."
mkdir -p /home/draxxy/dayhigh-daylow/logs
chmod 755 /home/draxxy/dayhigh-daylow/logs

# Copy service file
echo "Installing service file..."
sudo cp /home/draxxy/dayhigh-daylow/nifty-trading-bot.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/nifty-trading-bot.service

# Reload systemd
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable service (start on boot)
echo "Enabling service to start on boot..."
sudo systemctl enable nifty-trading-bot.service

echo ""
echo "======================================================================"
echo "✅ Installation Complete!"
echo "======================================================================"
echo ""
echo "Service Commands:"
echo "  Start:   sudo systemctl start nifty-trading-bot"
echo "  Stop:    sudo systemctl stop nifty-trading-bot"
echo "  Restart: sudo systemctl restart nifty-trading-bot"
echo "  Status:  sudo systemctl status nifty-trading-bot"
echo "  Logs:    sudo journalctl -u nifty-trading-bot -f"
echo ""
echo "Log Files:"
echo "  Standard: /home/draxxy/dayhigh-daylow/logs/bot.log"
echo "  Errors:   /home/draxxy/dayhigh-daylow/logs/bot-error.log"
echo ""
echo "⚠️  IMPORTANT: You need to generate Kite access token daily!"
echo "   Run: cd /home/draxxy/dayhigh-daylow && .venv/bin/python get_access_token.py"
echo ""
echo "To start the bot now, run:"
echo "  sudo systemctl start nifty-trading-bot"
echo "======================================================================"
