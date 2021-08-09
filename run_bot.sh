#!/bin/bash

# Source: https://askubuntu.com/questions/3299/how-to-run-cron-job-when-network-is-up
function check_online
{
    netcat -z -w 5 8.8.8.8 53 && echo 1 || echo 0
}

# How many times we should check if we're online - this prevents infinite looping
MAX_FAILURES=10
# Initial starting value for checks
PING_FAILURES=0

# Loop while we're not online.
IS_ONLINE=$(check_online)

while [ $IS_ONLINE -eq 0 ]; do
    # We're offline. Sleep for a bit, then check again
    sleep 10;
    IS_ONLINE=$(check_online)

    PING_FAILURES=$[ $PING_FAILURES + 1 ]
    if [ $PING_FAILURES -gt $MAX_FAILURES ]; then
        break
    fi
done

if [ $IS_ONLINE -eq 0 ]; then
    # We never were able to get online. Kill script.
    echo "run_bot.sh failed, could not detect a network connection"
    exit 1
fi

# Start the bot
(cd /root/RealTimeBot && python3 RealTimeBot.py) &
echo "run_bot.sh succeeded, bot has been initialized"
ps -aux | grep "RealTimeBot.py"
