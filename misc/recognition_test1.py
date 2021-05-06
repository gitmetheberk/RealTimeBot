import re
import logging

# Settings --------------------------------
SAFEMODE = True  # This should never be disabled, realistically speaking


# Advanced Settings -----------------------
VERSION = "2.0"  # Sets bot version, used when loading and writing json files
LOGGING_LEVEL = logging.DEBUG  # Sets the logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
# -----------------------------------------

# Logger config, https://stackoverflow.com/questions/28330317/print-timestamp-for-logging-in-python,
# https://stackoverflow.com/questions/13733552/logger-configuration-to-log-to-file-and-print-to-stdout
logging.basicConfig(filename="RealTimeBot.log",
                    #encoding="utf-8",
                    level=LOGGING_LEVEL,
                    datefmt='%Y-%m-%d %H:%M:%S',
                    format='%(asctime)s %(levelname)-8s %(message)s')

# Log to console as well as the file
logging.getLogger().addHandler(logging.StreamHandler())



# WORD LIST SETUP -------------------------------------------------------------------------
# Lists of words which may indicate a match
words_before_positive = ["to", "at", "around", "about", "for", "probably", "from"]
words_after_positive = ["am", "pm", "to"]

# Lists of words which may indicate the detection is not a time
words_before_negative = []
words_after_negative = ["minutes", "hours", "minute", "hour"]

# If SAFEMODE is disabled, add some riskier words
if not SAFEMODE:
    words_before_positive.extend([None, '', "like"])

#------------------------------------------------------------------------------------------

# Primary working pattern to parse messages
timeMatch_regex = re.compile("(\\b\\w*\\b)?\\s*([0-9]{1,2}:[0-9]{1,2}|[0-9]{1,4})\\s?([a-z]+|$)?", re.IGNORECASE)

while True:
    message = input()

    # TODO Implement the following checks/json interactions in the bot file
    # Check message sender isn't a bot or this bot
    # Check if message sender exists in database, if not print onetime welcome message and add with active false
    # If sender is in database, ensure they are active and have set timezone, else ignore

    # Strip commas
    message.replace(",", "")

    # Search for matches
    matches = re.findall(timeMatch_regex, message)

    logging.info("Processing message: " + message)

    # Check for matches
    if len(matches) is 0:
        logging.info("No matches found")
        continue

    # Message to send to server with converted times
    toSend = ""

    # Due to overlapping regex detection, this flag allows detection of times like "I'll be on from 8 to 9"
    to_prior = False

    # Look for times
    for match in matches:
        # match[0]: preceding word
        # match[1]: number, may contain colon
        # match[2]: following word

        logging.info("Processing match: " + str(match))

        # Boolean flags
        positive = False

        # Check for a colon, if found, skip this stage, else check words against list
        if ":" not in match[1]:
            # Check against negative words
            if match[0] in words_before_negative:
                logging.info("Negative word found, before, match aborted")
                continue
            elif match[2] in words_after_negative:
                logging.info("Negative word found, after, match aborted")
                continue

            # Check against positive words
            if (match[0] in words_before_positive) or (match[2] in words_after_positive):
                positive = True
        else:
            positive = True

        # Check if a positive match was found, if not check for safemode, abort match if safemode = True
        if not positive and SAFEMODE:
            logging.info("Safe mode enabled, match aborted")
            continue

        # Attempt to determine time
        time = str(match[1])  # Ease of use

        # Check for am/pm
        am_pm = -1
        if match[2] is "am":
            am_pm = 0
        elif match[2] is "pm":
            am_pm = 1

        hour = -1
        minute = -1

        # Time assignment block
        try:
            if ":" in time:
                time.split(':')
                hour = int(time[0])
                minute = int(time[1])
            else:
                # Attempt to split based on length of string
                if len(time) is 1:
                    hour = int(time)
                    minute = 0
                elif len(time) is 2:
                    hour = int(time)
                    minute = 0
                elif len(time) is 3:
                    hour = int(time[0])
                    minute = int(time[1:3])
                elif len(time) is 4:
                    hour = int(time[0:2])
                    minute = int(time[2:4])

        except Exception as e:
            logging.error("Exception in hour/minute assignment block", exc_info=e)
            continue

        logging.info("hour:{}, minute:{}, am_pm{}".format(hour, minute, am_pm))

        # This shouldn't be possible, but best to double check
        if hour is -1 or minute is -1:
            logging.error("hour or minute is -1 beyond the time assignment block, match aborted")
            continue

        # Validate times
        if minute > 59:
            logging.info("Invalid minute, match aborted")
            continue
        if am_pm is -1:
            if hour > 23:
                logging.info("Invalid hour, match aborted")
                continue
        else:
            if hour < 1 or hour > 12:
                logging.info("Invalid hour, match aborted")
                continue

