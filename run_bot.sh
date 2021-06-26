#!/bin/bash
python3 RealTimeBot.py &
echo "Bot has been initialized"
ps -aux | grep "python3 RealTimeBot.py"