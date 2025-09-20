import os, sys
import time
import atexit
from typing import Dict, List, Any
import logging
import asyncio
from os import getenv
import discord
from discord.ext import tasks,commands
import yt_dlp
# from dotenv import load_dotenv
import signal

# load_dotenv('./cfg/.env')


sys.path.append('.')
logging.basicConfig(level=logging.WARNING)
yt_dlp.utils.bug_reports_message = lambda: ''  # disable yt_dlp bug report
intents = discord.Intents.default()
# noinspection PyDunderSlots
intents.message_content = True
bot = commands.Bot(command_prefix='!',intents=intents, description='')

ytdl_format_options: dict[str, Any] = {'format': 'bestaudio',
                                       'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
                                       'restrictfilenames': True,
                                       'no-playlist': True,
                                       'nocheckcertificate': True,
                                       'ignoreerrors': False,
                                       'logtostderr': False,
                                       'geo-bypass': True,
                                       'quiet': True,
                                       'no_warnings': True,
                                       'default_search': 'auto',
                                       'source_address': '0.0.0.0',
                                       'no_color': True,
                                       'overwrites': True,
                                       'age_limit': 100,
                                       'live_from_start': True,
                                       'paths': {'home': f'./dl/'},
                                       'cookiefile': './cfg/cookies.txt'

                                       }

ffmpeg_options = {'options': '-vn -sn'}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
dlDir = ytdl_format_options['paths']['home']

class Source:
    """Parent class of all music sources"""

    def __init__(self, audio_source: discord.AudioSource, metadata):
        self.audio_source: discord.AudioSource = audio_source
        self.metadata = metadata
        self.title: str = metadata.get('title', 'Unknown title')
        self.url: str = metadata.get('url', 'Unknown URL')

    def __str__(self):
        return f'{self.title}\n{self.url}'


class YTDLSource(Source):
    """Subclass of YouTube sources"""

    def __init__(self, audio_source: discord.AudioSource, metadata):
        super().__init__(audio_source, metadata)
        self.url: str = metadata.get('webpage_url', 'Unknown URL')  # yt-dlp specific key name for original URL

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        try:
            loop = loop or asyncio.get_event_loop()
            metadata = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in metadata: metadata = metadata['entries'][0]
            filename = metadata['url'] if stream else ytdl.prepare_filename(metadata)
            return cls(await discord.FFmpegOpusAudio.from_probe(filename, **ffmpeg_options), metadata)
        except (PermissionError) as e:
            print('File already exists')
        


class ServerSession:
    def __init__(self, guild_id, voice_client, bot):
        self.guild_id: int = guild_id
        self.voice_client: discord.VoiceClient = voice_client
        self.queue: List[Source] = []
        self.bot = bot

    def display_queue(self) -> str:
        currently_playing = f'Currently playing: 0. {self.queue[0]}'
        return currently_playing + '\n' + '\n'.join([f'{i + 1}. {s}' for i, s in enumerate(self.queue[1:])])

    async def add_to_queue(self, ctx:commands.Context | None, url):  # does not auto start playing the playlist
        yt_source = await YTDLSource.from_url(url, loop=bot.loop, stream=False)  # stream=True has issues and cannot use Opus probing
        self.queue.append(yt_source)
        if self.voice_client.is_playing():
            await ctx.reply(f'Added to queue: ♪ {yt_source.title}\n{yt_source.url}')

    async def start_playing(self, ctx:commands.Context):
        self.voice_client.play(self.queue[0].audio_source, after=lambda e=None: self.sync_playback_error(ctx, e))
        await ctx.send(f'Now playing: ♪ {self.queue[0]}')

    def sync_playback_error(self, ctx, error: Exception):
        asyncio.run_coroutine_threadsafe(self.after_playing(ctx, error), self.bot.loop)

    async def after_playing(self, ctx:commands.Context, error):
        if error:
            raise error
        else:
            if self.queue:
                await self.play_next(ctx)

    async def play_next(self, ctx:commands.Context):  # should be called only after making the first element of the queue the song to play
        self.queue.pop(0)
        if self.queue:
            # await ctx.send(f'Now playing: ♪ {self.queue[0].title}\n{self.queue[0].url}')
            await self.voice_client.play(self.queue[0].audio_source, after=lambda e=None: self.sync_playback_error(ctx, e))



server_sessions: Dict[int, ServerSession] = {}  # {guild_id: ServerSession}


def clean_cache_files():
    if not server_sessions:  # only clean if no servers are connected
        for file in os.listdir(dlDir):
            if os.path.splitext(file)[1] in ['.webm', '.mp4', '.m4a', '.mp3', '.ogg'] and time.time() - os.path.getatime(os.path.join(dlDir, file)) > 7200:  # remove all cached webm files older than 2 hours
                # os.remove(file)
                print(file)




def get_res_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller
     Relative path will always get extracted into root!"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    if os.path.isfile(os.path.join(base_path, relative_path)):
        return os.path.join(base_path, relative_path)
    else:
        raise FileNotFoundError(f'Embedded file {os.path.join(base_path, relative_path)} is not found!')


@atexit.register
def cleanup():
    global server_sessions
    server_sessions = {}
    clean_cache_files()


@bot.event
async def on_ready():
    auto_cleanup.start()
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')


@tasks.loop(seconds=30)
async def auto_cleanup():
    global server_sessions
    for guild_id,session in server_sessions.copy().items():
        voice_client = session.voice_client
        if not voice_client.is_playing():
            if len(session.queue) == 0:
                await voice_client.disconnect()
                voice_client.cleanup()
                del server_sessions[guild_id]


async def connect_to_voice_channel(ctx:commands.Context, channel):
    voice_client = await channel.connect()
    if voice_client.is_connected():
        server_sessions[ctx.guild.id] = ServerSession(ctx.guild.id, voice_client, bot)
        await ctx.send(f'Connected to {voice_client.channel.name}.')
        return server_sessions[ctx.guild.id]
    else:
        await ctx.send(f'Failed to connect to voice channel {ctx.author.voice.channel.name}.')


@bot.hybrid_command(name='exit')
async def disconnect(ctx:commands.Context):
    """Disconnect from voice channel"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        voice_client = server_sessions[guild_id].voice_client
        await voice_client.disconnect()
        voice_client.cleanup()
        del server_sessions[guild_id]
        await ctx.send(f'Disconnected from {voice_client.channel.name}.')


@bot.hybrid_command()
async def pause(ctx:commands.Context):
    """Pause the current song"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        voice_client = server_sessions[guild_id].voice_client
        if voice_client.is_playing():
            voice_client.pause()
            await ctx.send('Paused')


@bot.hybrid_command()
async def resume(ctx:commands.Context):
    """Resume the current song"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        voice_client = server_sessions[guild_id].voice_client
        if voice_client.is_paused():
            voice_client.resume()
            await ctx.send('Resumed')


@bot.hybrid_command()
async def skip(ctx:commands.Context):
    """Skip the current song"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        session = server_sessions[guild_id]
        voice_client = session.voice_client
        if voice_client.is_playing():
            if len(session.queue) > 1:
                await ctx.send('Skipping')
                voice_client.stop()  # this will trigger after_playing callback and in that will call play_next so here no need call play_next
            else:
                await ctx.send('This is already the last item in the queue!')


@bot.hybrid_command(name='queue')
async def show_queue(ctx:commands.Context):
    """Show the current queue"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        await ctx.send(f'{server_sessions[guild_id].display_queue()}')


@bot.hybrid_command()
async def remove(ctx:commands.Context, index: int):
    """Remove an item from queue by index (1, 2...)"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        if index == 0:
            await ctx.send('Cannot remove current playing song, please use !skip instead.')
        elif index >= len(server_sessions[guild_id].queue):
            await ctx.send(f'The queue is not that long, there are only {len(server_sessions[guild_id].queue) - 1} items in the queue.')
        else:
            removed = server_sessions[guild_id].queue.pop(index)
            removed.audio_source.cleanup()
            await ctx.send(f'Removed {removed} from queue.')


@bot.hybrid_command()
async def clear(ctx:commands.Context):
    """Clear the queue and stop current song"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        voice_client = server_sessions[guild_id].voice_client
        server_sessions[guild_id].queue = []
        if voice_client.is_playing():
            voice_client.stop()
        await ctx.send('Queue cleared.')


@bot.hybrid_command()
async def song(ctx:commands.Context):
    """Show the current song"""
    guild_id = ctx.guild.id
    if guild_id in server_sessions:
        await ctx.send(f'Now playing {server_sessions[guild_id].queue[0]}')


@bot.hybrid_command()
async def play(ctx: commands.Context, query: str):
    """Search or Play YT"""

    await ctx.defer()
    guild_id = ctx.guild.id
    if guild_id not in server_sessions:  # not connected to any VC
        if ctx.author.voice is None:
            await ctx.send(f'You are not connected to any voice channel!')
            return
        else:
            session = await connect_to_voice_channel(ctx, ctx.author.voice.channel)
    else:  # is connected to a VC
        session = server_sessions[guild_id]
        if session.voice_client.channel != ctx.author.voice.channel:  # connected to a different VC than the command issuer (but within the same server)
            await session.voice_client.move_to(ctx.author.voice.channel)
            await ctx.send(f'Connected to {ctx.author.voice.channel}.')
    url = query
    await session.add_to_queue(ctx, url)  # will download file here
    if not session.voice_client.is_playing() and len(session.queue) <= 1:
        await session.start_playing(ctx)




async def main():
    async with bot:
        await bot.start(getenv('BOT_TOKEN'))

try:
    asyncio.run(main())
except (Exception, KeyboardInterrupt) as e:
    cleanup()
    print(e)
    raise SystemExit(e)