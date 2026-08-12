import discord
from discord.ext import commands
import sqlite3
import json
import asyncio
import urllib.parse
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, application_id=os.getenv("APPLICATION_ID"))

PAGE_SIZE = 10  # Number of summons displayed per page

# Initialize database
conn = sqlite3.connect("wish_history.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS wish_history (
                    user_id TEXT,
                    banner_type TEXT,
                    summon_data TEXT,
                    PRIMARY KEY (user_id, banner_type)
                 )''')
conn.commit()
conn.close()


def extract_authkey(url):

    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    return urllib.parse.unquote(query_params["authkey"][0]) if "authkey" in query_params else None


def fetch_full_summon_history(authkey, gacha_type):

    BASE_URL = "https://public-operation-hkrpg-sg.hoyoverse.com/common/gacha_record/api/getGachaLog"
    summon_history = []
    end_id = None  # Start without an `end_id`

    while True:
        params = {
            "authkey_ver": 1,
            "sign_type": 2,
            "lang": "en",
            "authkey": authkey,
            "game_biz": "hkrpg_global",
            "size": 20,  # Maximum per request
            "gacha_type": gacha_type,
        }
        if end_id:
            params["end_id"] = end_id  # Use `end_id` for pagination

        response = requests.get(BASE_URL, params=params)
        if response.status_code != 200:
            return summon_history  # Stop if API fails

        data = response.json().get("data", {})
        pulls = data.get("list", [])
        if not pulls:
            break  # Stop if no more pulls found

        summon_history.extend(pulls)
        end_id = pulls[-1]["id"]  # Update `end_id` to continue pagination

    return summon_history


def save_wish_history(user_id, banner_type, summon_data):

    conn = sqlite3.connect("wish_history.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO wish_history (user_id, banner_type, summon_data) VALUES (?, ?, ?)",
                   (user_id, banner_type, json.dumps(summon_data)))
    conn.commit()
    conn.close()


def clear_wish_history(user_id):

    conn = sqlite3.connect("wish_history.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wish_history WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()


@bot.command()
async def stats(ctx):

    conn = sqlite3.connect("wish_history.db")
    cursor = conn.cursor()

    banners = {
        "event": "Event",
        "weapon": "Weapon",
        "standard": "Standard"
    }

    standard_five_stars = {"Himeko", "Welt", "Bronya", "Gepard", "Bailu", "Clara", "Yanqing"}
    standard_lightcones = {"Something Irreplaceable", "Night on the Milky Way", "But the Battle Isn't Over",
                           "Moment of Victory", "Time Waits for No One", "Sleep Like the Dead",
                           "In the Name of the World"}

    embed = discord.Embed(title=f"📊 Warp Stats for {ctx.author.display_name}", color=discord.Color.blue())

    for banner_type, banner_name in banners.items():
        cursor.execute("SELECT summon_data FROM wish_history WHERE user_id = ? AND banner_type = ?",
                       (str(ctx.author.id), banner_type))
        result = cursor.fetchone()

        if not result:
            embed.add_field(name=f"{banner_name} Banner", value="⚠ No stored summon history.", inline=False)
            continue

        summon_data = json.loads(result[0])
        summon_data.reverse()  # Start from most recent pull

        pity_5_star = 0
        pity_4_star = 0
        last_5_star = None
        guaranteed_5_star = False
        guaranteed_weapon = False

        for summon in summon_data:
            pity_5_star += 1
            pity_4_star += 1

            if summon["rank_type"] == "5":
                last_5_star = summon["name"]
                if banner_type == "event":
                    guaranteed_5_star = last_5_star in standard_five_stars  # Check 50/50 status
                elif banner_type == "weapon":
                    guaranteed_weapon = last_5_star in standard_lightcones  # Check 75/25 status

                pity_5_star = 0  # Reset for next 5★
            elif summon["rank_type"] == "4":
                pity_4_star = 0  # Reset for next 4★

        pulls_until_next_5_star = max(0, 80 if banner_type == "weapon" else 90 - pity_5_star)
        pulls_until_next_4_star = max(0, 10 - pity_4_star)

        embed.add_field(name=f"{banner_name} Banner",
                        value=f"Pity (5★): {pity_5_star}/{'80' if banner_type == 'weapon' else '90'}\nPity (4★): {pity_4_star}/10",
                        inline=False)
        embed.add_field(name="Last 5★ Pull", value=last_5_star if last_5_star else "None", inline=False)

        if banner_type == "event":
            embed.add_field(name="50/50 Status",
                            value="Guaranteed next 5★ (Lost 50/50)" if guaranteed_5_star else "On 50/50",
                            inline=False)
        elif banner_type == "weapon":
            embed.add_field(name="75/25 Status",
                            value="Guaranteed event weapon (Lost 75/25)" if guaranteed_weapon else "On 75/25",
                            inline=False)

        embed.add_field(name="Warps until next 5★", value=pulls_until_next_5_star, inline=True)
        embed.add_field(name="Warps until next 4★", value=pulls_until_next_4_star, inline=True)

    conn.close()
    await ctx.send(embed=embed)


@bot.command()
async def average(ctx):

    banners = {
        "event": ("Event", 90),
        "weapon": ("Weapon", 80),
        "standard": ("Standard", 90)
    }

    embed = discord.Embed(title=f"📊 5★ Pull Statistics for {ctx.author.display_name}", color=discord.Color.gold())
    conn = sqlite3.connect("wish_history.db")
    cursor = conn.cursor()

    for banner_type, (banner_name, max_pity) in banners.items():
        cursor.execute("SELECT summon_data FROM wish_history WHERE user_id = ? AND banner_type = ?",
                       (str(ctx.author.id), banner_type))
        result = cursor.fetchone()

        if not result:
            embed.add_field(name=f"{banner_name} Banner", value="No data available", inline=False)
            continue

        summon_data = json.loads(result[0])
        chronological_pulls = list(reversed(summon_data))  # Oldest first

        five_star_history = []
        pity_counter = 0

        for summon in chronological_pulls:
            pity_counter += 1
            if summon["rank_type"] == "5":
                five_star_history.append({
                    "name": summon["name"],
                    "pity": pity_counter
                })
                pity_counter = 0  # Reset counter

        if not five_star_history:
            banner_value = "No 5★ pulls recorded"
        else:
            total_pity = sum(star["pity"] for star in five_star_history)
            average_pity = total_pity / len(five_star_history)
            pulls_list = "\n".join(
                f"{star['name']} ({star['pity']}/{max_pity})"
                for star in reversed(five_star_history)  # Newest first
            )
            banner_value = f"**Average:** {average_pity:.1f} pulls\n{pulls_list}"

        embed.add_field(name=f"{banner_name} Banner", value=banner_value, inline=False)

    conn.close()
    await ctx.send(embed=embed)


# Slash Command: /importwarp
@bot.tree.command()
async def importwarp(interaction: discord.Interaction, url: str):

    await interaction.response.defer()

    authkey = extract_authkey(url)
    if not authkey:
        await interaction.followup.send(
            f"Invalid URL, {interaction.user.mention}! Please make sure the URL is correct.")
        return

    gacha_types = {"standard": 1, "event": 11, "weapon": 12}
    all_summon_data = {}

    for banner, gacha_type in gacha_types.items():
        summon_data = fetch_full_summon_history(authkey, gacha_type)
        if summon_data:
            all_summon_data[banner] = summon_data
            save_wish_history(str(interaction.user.id), banner, summon_data)

    if not all_summon_data:
        await interaction.followup.send(f"No summon history found for {interaction.user.mention}.")
    else:
        await interaction.followup.send(f"Successfully imported summon history for {interaction.user.mention}!")


# Prefix Command: !warp
@bot.command()
async def warp(ctx, banner_type: str):

    conn = sqlite3.connect("wish_history.db")
    cursor = conn.cursor()

    cursor.execute("SELECT summon_data FROM wish_history WHERE user_id = ? AND banner_type = ?",
                   (str(ctx.author.id), banner_type.lower()))
    result = cursor.fetchone()
    conn.close()

    if not result:
        await ctx.send(f"No stored summon history found for {ctx.author.mention}. Use `/importwarp <url>` first.")
        return

    summon_data = json.loads(result[0])
    pages = [summon_data[i:i + PAGE_SIZE] for i in range(0, len(summon_data), PAGE_SIZE)]
    current_page = 0

    def format_page(page):


        def get_star_rating(star):
            if star == "5":
                return f"(5⭐️)"
            elif star == "4":
                return f"(4⭐️)"
            return ""

        return "\n".join(
            f"{get_star_rating(summon['rank_type'])} {summon['name']} ({summon['item_type']}) | {summon['time']}"
            for summon in page)

    embed = discord.Embed(title=f"📜 {banner_type.capitalize()} Warp History for {ctx.author.display_name}",
                          description=format_page(pages[current_page]), color=discord.Color.green())
    embed.set_footer(text=f"Page {current_page + 1}/{len(pages)}")
    message = await ctx.send(embed=embed)
    await message.add_reaction("⬅️")
    await message.add_reaction("➡️")

    def check(reaction, user):
        return user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in ["⬅️", "➡️"]

    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=30, check=check)
            if str(reaction.emoji) == "⬅️" and current_page > 0:
                current_page -= 1
            elif str(reaction.emoji) == "➡️" and current_page < len(pages) - 1:
                current_page += 1
            else:
                continue

            embed.description = format_page(pages[current_page])
            embed.set_footer(text=f"Page {current_page + 1}/{len(pages)}")
            await message.edit(embed=embed)
            await message.remove_reaction(reaction.emoji, user)
        except asyncio.TimeoutError:
            break


# Prefix Command: !clear
@bot.command()
async def clear(ctx):
    try:
        clear_wish_history(ctx.author.id)
        await ctx.send(f"Successfully cleared your wish history, {ctx.author.mention}!")
    except Exception as e:
        await ctx.send(f"An error occurred while clearing your history: {str(e)}")


@bot.event
async def on_ready():
    print(f"Bot is online! Logged in as {bot.user}")
    await bot.tree.sync()

bot.run(os.getenv("DISCORD_TOKEN"))
