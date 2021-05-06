from discord.ext import commands
import discord
import json
import os
import re
import datetime
import pytz
import logging
from dotenv import load_dotenv

# Settings -------------------------------------------------------------------------
SAFEMODE = True  # This should never be disabled, realistically speaking
BOT_PREFIX = '-'  # Sets the prefix character(s) for bot commands

# Advanced Settings ----------------------------------------------------------------
VERSION = "2.0"  # Sets bot version, used when loading and writing json files
LOGGING_LEVEL = logging.INFO  # Sets the logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Initialization -------------------------------------------------------------------
# Get token from environment variable
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Variables to store data from guilds.json
guilds = {}

# Logger config, https://stackoverflow.com/questions/28330317/print-timestamp-for-logging-in-python,
# https://stackoverflow.com/questions/13733552/logger-configuration-to-log-to-file-and-print-to-stdout
logging.basicConfig(filename="RealTimeBot.log",
                    # encoding="utf-8",
                    level=LOGGING_LEVEL,
                    datefmt='%Y-%m-%d %H:%M:%S',
                    format='%(asctime)s %(levelname)-8s %(message)s')

logging.getLogger().addHandler(logging.StreamHandler())  # Log to console as well as the file

# Word List & Regex Setup -----------------------------------------------------------------
# TODO Add ability to modify these lists with commands
# Lists of words which may indicate a match
words_before_positive = ["at", "around", "about", "for", "probably", "from", "by", "until"]
words_after_positive = ["am", "pm", "to"]

# Lists of words which may indicate the detection is not a match
words_before_negative = ["in"]
words_after_negative = ["minutes", "hours", "minute", "hour", "min", "mins", "days", "weeks", "months", "years"]

# If SAFEMODE is disabled, add some riskier words
if not SAFEMODE:
    words_before_positive.extend(['', "like"])

# Regex patterns for the on_message handler
timeMatch_regex = re.compile("(\\b\\w*\\b)?\\s*([0-9]{1,2}:[0-9]{1,2}|[0-9]{1,4})\\s?([a-z]+|$)?", re.IGNORECASE)
timeMatch_removeDecimal = re.compile("[0-9]+\\.[0-9]+")

# Bot initialization
bot = commands.Bot(command_prefix=BOT_PREFIX)

@bot.event
async def on_ready():
    logging.info("Connection established: " + str(bot.user))

    # Load users.json and guilds.json
    global guilds
    try:
        file_guilds = open("guilds.json", 'r')
        guilds = json.load(file_guilds)
        file_guilds.close()

        # guilds.json notes:
        # Outermost level: Guild IDs
        # Next level: "timezones" and "users"
        # timezones --> contains all server timezones which need to be displayed
        # users --> User IDs
        # Next level: "timezone" and "active"
        # timezone --> User's timezone
        # active --> User's opt-in/opt-out status, boolean

    except:
        logging.exception("An error occurred while loading guilds.json")
        logging.critical("This program will now terminate")
        exit(0)

    # Check json version
    if not str(guilds["version"]) == VERSION:
        logging.warning("guilds.json version is {}, RealTimeBot.py version is {}, errors may occur".format(guilds["version"], VERSION))


# Bot events -------------------------------------------------------------------------------
@bot.event
async def on_guild_join(guild):
    # Create a record for this guild in guilds if one doesn't exist already
    if not str(guild.id) in guilds:
        guilds[str(guild.id)] = {"timezones": [], "users": {}}

    logging.info("Created new guild record for guild: {}".format(guild.id))

@bot.event
async def on_message(message):
    # Grab the message out of the context object
    message_content = str(message.content)

    # Temporary handler to protect DBS
    # if str(str(message.guild.id)) is not "283141733896945664":
    #     return

    # Check for a bot message
    if message.author.bot:
        logging.debug("Disregarding bot message")
        return

    # Check for commands
    if message_content.startswith(BOT_PREFIX):
        logging.debug("on_message sending to process_commands due to BOT_PREFIX")
        await bot.process_commands(message)
        return

    # Strip commas, convert to lowercase, remove decimals
    message_content.replace(",", "")
    message_content = message.content.lower()
    message_content = re.sub(timeMatch_removeDecimal, '', message_content)

    # Search for matches
    matches = re.findall(timeMatch_regex, message_content)
    logging.debug("Processing message: " + message_content)

    # Check for matches
    if len(matches) is 0:
        logging.info("No matches found in message: " + message_content)
        return

    # At least one possible match, check the user
    userStatus = checkUser(str(message.author.id), str(message.guild.id))
    if userStatus is -1:
        logging.error("Aborting time conversion for user {} due to invalid userStatus return".format(message.author.id))
        return
    elif userStatus is 0:
        await message.channel.send("Howdy, {}! If you would like to opt-in to automatic timezone conversion for your messages, use '-timezone est|cst|mt|pst' to set your timezone".format(message.author.name))
    elif userStatus is 1:
        # User has opted out, return
        logging.info("Ignoring message, user has opted out")
        return
    #elif userStatus is 2:
        # User has opted in, continue

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

        # Check for to/to_prior
        if to_prior:
            to_prior = False
            positive = True
        if "to" in match[2]:
            to_prior = True

        # Check if a positive match was found, if not check for safemode, abort match if safemode = True
        if not positive and SAFEMODE:
            logging.info("Safe mode enabled, match aborted")
            continue

        # Attempt to determine time
        time = str(match[1])  # Ease of use

        # Check for am/pm
        am_pm = -1
        if match[2] == "am":
            am_pm = 0
        elif match[2] == "pm":
            am_pm = 1

        hour = -1
        minute = -1

        # Time assignment block
        try:
            if ":" in time:
                time = time.split(':')
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

        logging.debug("hour:{}, minute:{}, am_pm:{}".format(hour, minute, am_pm))

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

        # Grab the sender's timezone
        sender_TZ = pytz.timezone(guilds[str(message.guild.id)]["users"][str(message.author.id)]["timezone"])

        # If am_pm not specified by user, guess
        if am_pm is -1 and hour < 13:
            currentTime = datetime.datetime.now(sender_TZ)
            currentHour = currentTime.hour
            if currentHour > 12:
                currentHour = currentTime.hour - 12

            # If hour > currentHour, am/pm == am/pm local time
            if hour > currentHour or (hour == currentHour and minute >= currentTime.minute):
                if currentTime.hour < 12:
                    am_pm = 0
                else:
                    am_pm = 1
            else:
                if currentTime.hour < 12:
                    am_pm = 1
                else:
                    am_pm = 0
            logging.debug("am_pm guess: {}".format(am_pm))

        # Formatting
        if len(toSend) is not 0:
            toSend += "\n"
        toSend += "**"

        # Print and conversion block
        # Convert current time to 24 hour based on am/pm
        if am_pm == 1 and hour != 12:
            hour += 12
        elif am_pm == 0 and hour == 12:
            hour = 0

        # Create localized DT for the sender (date is irrelevant... theoretically)
        sender_DT = sender_TZ.localize(datetime.datetime(2020, 12, 20, hour, minute))

        # Loop through all registered timezones for this guild, append to outgoing message
        for zone in guilds[str(message.guild.id)]["timezones"]:
            updatedTime = sender_DT.astimezone(pytz.timezone(zone))
            toSend += "{}: {}   ".format(zone, updatedTime.strftime("%I:%M%p").lower())
        toSend += '**'

    if len(toSend) != 0:
        logging.info("Processing complete, sending message: " + toSend)
        await message.channel.send(toSend)
    else:
        logging.info("No times detected")

# Bot commands -----------------------------------------------------------------------------
class Timezones(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="opt_out", help="Opt-out of automatic timezone conversion")
    async def opt_out(self, ctx):
        authorID = str(ctx.message.author.id)
        guildID = str(ctx.guild.id)

        # Check if a record exists for this user, if not create one
        if str(authorID) not in guilds[guildID]["users"]:
            createInactiveRecord(authorID, guildID)

        logging.info("Active status for {} set to False".format(authorID))
        
        # Check for ricky bobby
        if str(authorID) != "324353466485178368":
            guilds[guildID]["users"][str(authorID)]["active"] = False
        else:
            await ctx.message.add_reaction('\U0001F44E')
            return
        

        # Update guilds -- Don't need to update on an opt_out since it doesn't change anything
        #updateGuilds(guildID)

        #await ctx.send("You have been opted-out of automatic timezone conversion.")
        await ctx.message.add_reaction('\U0001F44D')

    @commands.command(name="opt_in", help="Opt-in to automatic timezone conversion")
    async def opt_in(self, ctx):
        # Check if a record exists for this user, if not, the user should use set_tz
        authorID = str(ctx.message.author.id)
        guildID = str(ctx.guild.id)
        if str(authorID) not in guilds[guildID]["users"]:
            await ctx.send('Because you have not set your timezone before, please use -timezone to opt-in')
            return

        logging.info("Active status for {} set to True".format(authorID))
        guilds[guildID]["users"][str(authorID)]["active"] = True

        # Update guilds
        updateGuilds(guildID)

        #await ctx.send('You have been opted-in to automatic timezone conversion!')
        await ctx.message.add_reaction('\U0001F44D')


    @commands.command(name="timezone", help="east/est, central/cst, mountain/mt, pacific/pst", pass_context=True)
    async def set_timezone(self, ctx, *, args):
        authorID = str(ctx.message.author.id)
        guildID = str(ctx.guild.id)
        args = args.lower()

        # Decode timezone
        if args == 'est' or args == 'east':
            zone = 'US/Eastern'
        elif args == 'cst' or args == 'central':
            zone = 'US/Central'
        elif args == 'mst' or args == 'mountain':
            zone = 'US/Mountain'
        elif args == 'pst' or args == 'pacific':
            zone = 'US/Pacific'
        elif "hammer" in args:
            await ctx.send("Stop, Hammer Time!")
            return
        else:
            # Notify the user the requested timezone is invalid
            logging.info("Could not resolve timezone: {}".format(args))
            await ctx.send('Error: {} is not a valid timezone'.format(args))
            return

        # Check if a record already exists for this user, otherwise create a new one
        if str(authorID) in guilds[guildID]["users"]:
            guilds[guildID]["users"][authorID]["timezone"] = zone
            guilds[guildID]["users"][authorID]["active"] = True
            #await ctx.send('Your timezone has been updated to {}'.format(zone))
            await ctx.message.add_reaction('\U0001F44D')
        else:
            guilds[guildID]["users"][str(authorID)] = {}
            guilds[guildID]["users"][authorID]["timezone"] = zone
            guilds[guildID]["users"][authorID]["active"] = True
            #await ctx.send('Your timezone has been saved as {}'.format(zone))
            await ctx.message.add_reaction('\U0001F44D')

        logging.info("Timezone for {} has been saved as {}".format(authorID, zone))

        # Update guilds
        updateGuilds(guildID)


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping', help="Verify bot responsiveness")
    async def ping(self, ctx):
        logging.info("Bot responding to ping (test)")
        await ctx.send('pong! Bot is alive')

    @commands.command(name='stop', help="Kills the bot, requires developer privileges")
    async def stop(self, ctx):
        if str(ctx.message.author.id) == "192872910103248897":
            logging.info("Stop command received from authorized user, shutting down")
            saveGuilds()
            exit(1)
        else:
            logging.info("Unauthorized stop command attempted by user: {} with name: {} on guild: {} with name: {}".format(ctx.message.author.id, ctx.message.author.name, ctx.guild.id, ctx.guild.name))


# Register cogs
bot.add_cog(Timezones(bot))
bot.add_cog(Other(bot))


# Miscellaneous functions --------------------------------------------------------------------------
# Updates guilds and saves the updated guild to a file
def updateGuilds(guildID):
    global guilds
    guildID = str(guildID)

    # Loop through all timezones registered for a guild, find all unique zones
    timezones = []
    for userID in guilds[guildID]["users"]:
        if guilds[guildID]["users"][userID]["timezone"] not in timezones:
            if guilds[guildID]["users"][userID]["timezone"] is not None:
                timezones.append(guilds[guildID]["users"][userID]["timezone"])

    guilds[guildID]["timezones"] = timezones
    saveGuilds()


# Save guilds to guilds.json
def saveGuilds():
    file = open('guilds.json', 'w+')
    json.dump(guilds, file)
    file.close()


# Used in on_message handler to verify a user is active, returns status code 0, 1, or 2
# 0 = user not registered in database, 1 = user inactive, 2 = user active
def checkUser(authorID, guildID):
    guildID = str(guildID)
    authorID = str(authorID)

    # Check if this user has a record for this guild
    if authorID not in guilds[guildID]["users"]:
        # No record exists, create an inactive record and return 0
        createInactiveRecord(authorID, guildID)
        return 0
    elif not guilds[guildID]["users"][authorID]["active"]:
        return 1
    elif guilds[guildID]["users"][authorID]["active"]:
        return 2
    else:
        logging.error("checkUser() has failed to satisfy an if statement")
        return -1


# Creates an inactive user record
def createInactiveRecord(userID, guildID):
    global guilds
    logging.info("Creating user record for {}".format(userID))
    guilds[guildID]["users"][str(userID)] = {}
    guilds[guildID]["users"][str(userID)]["timezone"] = None
    guilds[guildID]["users"][str(userID)]["active"] = False


# Run the bot
bot.run(TOKEN)
