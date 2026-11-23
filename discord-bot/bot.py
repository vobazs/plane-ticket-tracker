import os
import aiohttp
import discord
from discord.ext import commands

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WEB_API_URL = os.getenv("WEB_API_URL", "http://web-api:8000")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (connected to {WEB_API_URL})")


@bot.command()
async def routes(ctx):
    """Listázza az összes figyelt járatot: !routes"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{WEB_API_URL}/routes") as resp:
            if resp.status != 200:
                await ctx.send(f"Hiba a lekérdezésnél: {resp.status}")
                return
            data = await resp.json()

    if not data:
        await ctx.send("Még nincs felvett járat.")
        return

    lines = [
        f"**#{r['id']}** `{r['origin']} -> {r['destination']}` | Dátum: `{r['outbound_date']}` | Célár: **{r['target_price']} HUF**"
        for r in data
    ]
    await ctx.send("\n".join(lines))


@bot.command()
async def add(ctx, origin: str, destination: str, outbound_date: str, target_price: int):
    """Új járat felvétele: !add BUD BCN 2027-03-15 35000"""
    payload = {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "outbound_date": outbound_date,
        "target_price": target_price,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{WEB_API_URL}/routes", json=payload) as resp:
            if resp.status != 201:
                text = await resp.text()
                await ctx.send(f"Nem sikerült felvenni ({resp.status}): `{text}`")
                return
            r = await resp.json()

    await ctx.send(
        f"Járat felvéve! **#{r['id']}** `{r['origin']} -> {r['destination']}` ({r['outbound_date']}), célár: **{r['target_price']} HUF**"
    )


@bot.command()
async def prices(ctx, route_id: int):
    """Ártörténet lekérdezése: !prices 1"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{WEB_API_URL}/routes/{route_id}/prices") as resp:
            if resp.status != 200:
                await ctx.send(f"Hiba ({resp.status}) – biztos létezik a #{route_id} járat?")
                return
            data = await resp.json()

    if not data:
        await ctx.send(f"A #{route_id} járathoz még nincs mentett ár.")
        return

    lines = [f"- **{p['price']} HUF** (`{p['checked_at'][:16].replace('T', ' ')}`)" for p in data[:10]]
    await ctx.send(f"**#{route_id} utolsó árai:**\n" + "\n".join(lines))

@bot.command()
async def check(ctx, route_id: int):
    """Azonnali élő árlekérdezés: !check 1"""
    await ctx.send(f"⏳ Élő ár lekérdezése a **#{route_id}** járathoz...")
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{WEB_API_URL}/routes/{route_id}/check") as resp:
            if resp.status != 200:
                text = await resp.text()
                await ctx.send(f"Hiba ({resp.status}): `{text}`")
                return
            r = await resp.json()

    status = "🔥 **CÉLÁR ALATT!**" if r["price"] <= r["target_price"] else "ℹ️ Még a célár felett van."
    await ctx.send(
        f"✈️ **#{r['route_id']}** `{r['origin']} -> {r['destination']}` ({r['outbound_date']})\n"
        f"Aktuális ár: **{r['price']} HUF** (Célár: {r['target_price']} HUF)\n{status}"
    )

@bot.command()
async def delete(ctx, route_id: int):
    """Járat törlése: !delete 1"""
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{WEB_API_URL}/routes/{route_id}") as resp:
            if resp.status == 404:
                await ctx.send(f"Nem található **#{route_id}** azonosítójú járat.")
                return
            if resp.status != 200:
                text = await resp.text()
                await ctx.send(f"Hiba ({resp.status}): `{text}`")
                return
    await ctx.send(f"🗑️ A **#{route_id}** járat (és az árelőzményei) törölve.")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is missing!")
    bot.run(DISCORD_TOKEN)
