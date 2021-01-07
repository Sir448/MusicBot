import discord
import youtube_dl
import os
from os import system
from os.path import join, dirname
from dotenv import load_dotenv
from discord.ext import commands
from discord import FFmpegPCMAudio
from random import randint
import spotify
import json
import requests
import spotipy.util as util
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import asyncio

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

token = os.getenv("TOKEN")
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

api_service_name = "youtube"
api_version = "v3"
api_key = os.getenv("API_KEY")

youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey = api_key)

bot = commands.Bot(command_prefix="/")

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

answer = None
startMessage = None
players = {}
songPos = []
response_json = None
songNumber = 0
winner = None
gamePrompted = False
gameStarted = False
voice = None
Endgame = False

def get_song(pos, response_json):
    id = response_json["items"][pos]["track"]["id"]
    name = None
    if " (" in response_json["items"][pos]["track"]["name"] and " -" in response_json["items"][pos]["track"]["name"]:
        name = response_json["items"][pos]["track"]["name"][:min(response_json["items"][pos]["track"]["name"].find(" ("),response_json["items"][pos]["track"]["name"].find(" -"))]
    elif " (" in response_json["items"][pos]["track"]["name"]:
        name = response_json["items"][pos]["track"]["name"][:response_json["items"][pos]["track"]["name"].find(" (")]
    elif " -" in response_json["items"][pos]["track"]["name"]:
        name = response_json["items"][pos]["track"]["name"][:response_json["items"][pos]["track"]["name"].find(" -")]
    else:
        name = response_json["items"][pos]["track"]["name"]

    artists = response_json["items"][pos]["track"]["artists"]

    with open('songList.json', 'r') as f:
        songList = json.load(f)
    
    if id not in songList:
        print("downloading new song")
        search = name

        songList[id] = {
            "name": name,
            "artists": []
        }

        for artist in artists:
            songList[id]["artists"].append(artist["name"])
            search += " " + artist["name"]
        
        with open('songList.json', 'w') as f:
            json.dump(songList, f, indent = 4) 

        search += " audio"
        
        request = youtube.search().list(
            part="id",
            maxResults=1,
            q=search,
            type="video",
            videoCategoryId="10"
        )
        response = request.execute()

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'D:/MusicBot/Songs/{}.mp3'.format(id),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download(["https://www.youtube.com/watch?v={}\n".format(response["items"][0]["id"]["videoId"])])


@bot.command(pass_context=True)
async def start(ctx, number, url):
    global startMessage, players, songPos, response_json, gamePrompted, gameStarted
    if not gameStarted:
        gamePrompted = True
        players.clear()
        print(url)
        embed = discord.Embed(title = "Music Quiz", description="Be the first person to guess the name of the song.\n\nReact to this message to play. Use the command `/ready` to start the game.", color = 0xFF0000)
        startMessage = await ctx.send(embed=embed)
        await startMessage.add_reaction('✅')

        stoken = util.prompt_for_user_token(username = "sirawesomeness789", client_id = client_id, client_secret = client_secret, redirect_uri = "http://example.com")
        query = "https://api.spotify.com/v1/playlists/{}/tracks".format(url[-22:])

        response = requests.get(
            query,
            headers = {
                "Content-Type": "appliation/json",
                "Authorization": "Bearer {}".format(stoken)
            })
        response_json = response.json()

        songPos = []

        # print(response_json["items"])
        number = int(number)
        if number > len(response_json["items"]):
            number = len(response_json["items"])
            embed.set_footer(text = "There are only {} songs in the playlist so there will only be {} rounds".format(len(response_json["items"]),len(response_json["items"])))
            await startMessage.edit(embed = embed)
        while(len(songPos) < number):
            pos = randint(0,len(response_json["items"])-1)
            if pos not in songPos:
                songPos.append(pos)

        for pos in songPos[:5]:
            get_song(pos, response_json)

        print("Game Ready")
        
        await asyncio.sleep(90)
        startMessage = None
        gamePrompted = False
        return
    else:
        embed = discord.Embed(description="Game is currently in progress.", color = 0xFF0000)
        await ctx.send(embed=embed)


@bot.event
async def on_reaction_add(reaction, user):
    global players, gamePrompted, gameStarted
    if reaction.message.id == startMessage.id and user.id not in players and not user.bot and gamePrompted and not gameStarted:
        players[user.id] = 0
        print(players)

@bot.event
async def on_reaction_remove(reaction, user):
    global players, gamePrompted, gameStarted
    if reaction.message.id == startMessage.id and gamePrompted and not gameStarted:
        players.pop(user.id, None)

def play_next(ctx):
    global response_json, players, songPos, winner, answer, gameStarted, voice, songNumber, Endgame
    answer = None
    id = response_json["items"][songPos[songNumber]]["track"]["id"]
    with open('songList.json', 'r') as f:
        songList = json.load(f)
    if winner != None:
        title = "{} won that round".format(winner)
    else:
        title = "No one won that round"
    description = "{} by ".format(songList[id]["name"])
    if len(songList[id]["artists"]) == 1:
        description += songList[id]["artists"][0]
    elif len(songList[id]["artists"]) == 2:
        description += "{} and {}".format(songList[id]["artists"][0],songList[id]["artists"][1])
    elif len(songList[id]["artists"]) > 2:
        for artist in songList[id]["artists"]:
            if artist != songList[id]["artists"][-1]:
                description += "{}, ".format(artist)
            else:
                description += "and {}".format(artist)

    embed = discord.Embed(title = title, description=description, color = 0xFF0000)

    if songNumber + 1 < len(songPos):
        sortedPlayers = sorted(players.items(), key=lambda x: x[1], reverse = True)
        value = ""
        for player in sortedPlayers:
            value += "{}: {}\n".format(bot.get_user(player[0]).name, player[1])

        embed.add_field(name = "Points", value = value, inline = False)
    asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)

    songNumber += 1
    if Endgame:
        songNumber = len(songPos)

    if songNumber < len(songPos):
        id = response_json["items"][songPos[songNumber]]["track"]["id"]
        winner = None
        answer = songList[id]["name"]
        voice.play(discord.FFmpegPCMAudio("./Songs/{}.mp3".format(response_json["items"][songPos[songNumber]]["track"]["id"])), after = lambda e: play_next(ctx))
        if songNumber + 5 <= len(songPos):
            get_song(songPos[songNumber + 4], response_json)
    else:
        gameStarted = False
        sortedPlayers = sorted(players.items(), key= lambda x: x[1], reverse = True)
        n = 0
        if len(players) > 1:
            while sortedPlayers[n][1] == sortedPlayers[n+1][1]:
                n+=1
        title = ""
        if n == 0:
            title = "{} wins!".format(bot.get_user(sortedPlayers[0][0]).name)
        elif n == 1:
            title = "{} and {} tied!".format(bot.get_user(sortedPlayers[0][0]).name, bot.get_user(sortedPlayers[1][0]).name)
        elif n > 1:
            for player in sortedPlayers[:n+1]:
                if player != sortedPlayers[n]:
                    title += "{}, ".format(bot.get_user(player[0]).name)
                else:
                    title += "and {} tied!".format(bot.get_user(player[0]).name)

        embed = discord.Embed(title = title, color = 0xFF0000)

        value = ""
        for player in sortedPlayers:
            value += "{}: {}\n".format(bot.get_user(player[0]).name, player[1])
            
        embed.add_field(name = "Points", value = value, inline = False)
        asyncio.run_coroutine_threadsafe(ctx.send(embed=embed), bot.loop)
        asyncio.run_coroutine_threadsafe(voice.disconnect(), bot.loop)


@bot.command()
async def ready(ctx):
    global songNumber, winner, gamePrompted, gameStarted, players, answer, startMessage, response_json, songPos, voice
    
    if len(players) > 0 and gamePrompted and not gameStarted:
        try:
            vc = ctx.message.author.voice.channel
            voice = await vc.connect()
            description = "**Players:**"
            for player in players.keys():
                description += "\n"+str(bot.get_user(player).name)
            embed = discord.Embed(title = "Starting game", description=description, color = 0xFF0000)
            await ctx.send(embed=embed)
            songNumber = 0
            winner = None
            startMessage = None
            gamePrompted = False
            gameStarted = True
            with open('songList.json', 'r') as f:
                songList = json.load(f)
            answer = songList[response_json["items"][songPos[songNumber]]["track"]["id"]]["name"]
            voice.play(discord.FFmpegPCMAudio("./Songs/{}.mp3".format(response_json["items"][songPos[songNumber]]["track"]["id"])), after = lambda e: play_next(ctx))
        except:
            embed = discord.Embed(description="Please join a voice channel to start the game", color = 0xFF0000)
            await ctx.send(embed=embed)
    elif len(players) == 0:
            embed = discord.Embed(description="You need more players to start the game. React to the start message to join the game.", color = 0xFF0000)
            await ctx.send(embed=embed)
    elif gameStarted:
            embed = discord.Embed(description="Game is currently in progress.", color = 0xFF0000)
            await ctx.send(embed=embed)
    elif not gamePrompted:
            embed = discord.Embed(description="No game has been started.", color = 0xFF0000)
            await ctx.send(embed=embed)

@bot.command()
async def endgame(ctx):
    global songNumber, songPos, winner, gameStarted, voice, Endgame
    if gameStarted:
        winner = None
        Endgame = True
        voice.stop()
    else:
        embed = discord.Embed(description="No game has been started.", color = 0xFF0000)
        await ctx.send(embed=embed)

@bot.command()
async def skip(ctx):
    global winner, gameStarted, voice
    if gameStarted:
        winner = None
        voice.stop()
    else:
        embed = discord.Embed(description="No game has been started.", color = 0xFF0000)
        await ctx.send(embed=embed)

@bot.command()
async def answer(ctx):
    global answer
    print(answer)

@bot.event
async def on_message(message):
    global gameStarted, players, answer, winner, voice
    # print(f"message: {message.content}")
    # print(f"answer: {answer}")
    if gameStarted and message.author.id in players and message.content.lower() == answer.lower():
        winner = message.author.name
        players[message.author.id] += 1
        voice.stop()
    await bot.process_commands(message)



@bot.command()
async def test(ctx):
    global startMessage
    embed = discord.Embed(title = "Sir won that round", description="Focus by Ariana Grande", color = 0xFF0000)
    embed.add_field(name = "Points", value = "Sir: 3\nBot: 0", inline = False)
    startMessage = await ctx.send(embed=embed)
    await startMessage.add_reaction('✅')

@bot.command()
async def test2(ctx):
    global players
    description = "Players:"
    for player in players.keys():
        description += "\n"+str(bot.get_user(player).name)
    await ctx.send(description)


@bot.command()
async def play(ctx, url):
    vc = ctx.message.author.voice.channel
    voice = await vc.connect()
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'D:/MusicBot/Songs/song.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    for file in os.listdir("./Songs"):
        if file[-4:] == ".mp3":
            os.rename(os.path.join("./Songs", file), "Songs/test.mp3")
    voice.play(discord.FFmpegPCMAudio("./Songs/test.mp3"), after = lambda e: asyncio.run_coroutine_threadsafe(ctx.send("test"), bot.loop))


# get playlist from spotify
    #randomly choose x amount of songs
    #put those into yt playlist
# download a queue of 5 Songs
# add point system
# add guessing system
# add react to join game
# add end game


# game starts
# makes a list of x number of random songs from spotify playlist
# check first 5 songs of list
#     if song has not been queried before, query and download song
#         add song to list of previously queried songs
#     if song has been downloaded before, fetch song from downloads
# when song is guessed, next song is query and downloaded
# repeat until none is left

# if it's the first song, play the song
# start timer
# song is guessed give point and say who won
# say what the song was
# download/play next song, restart timer
    #must check if there are anymore songs

#ending the game:
# disconnect
# say who won and what the points were

# end of song:
# song has been guessed or skipped
# song has ended

bot.run(token)
