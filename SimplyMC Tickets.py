from discord.ext import commands
from discord import app_commands
import discord
from discord import ui
import os
import io
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

TICKET_CATEGORIES = {
    "General Support": "🎛 General Support",
    "Player Report": "🚨 Player Reports",
    "Inventory Refund": "🎒 Inventory Refunds",
    "Punishment Appeal": "⚖️ Punishment Appeals",
    "Development Issue": "🚾 Development Issues",
    "Store Issue": "🛒 Store Issues",
    "Staff Report": "🧑‍💼 Staff Reports"
}

TRANSCRIPT_CHANNEL_NAME = "ticket-transcripts"

MODAL_QUESTIONS = {
    "General Support": [
        ("What is your username?", discord.TextStyle.short),
        ("On what server do you need support?", discord.TextStyle.short)
    ],
    "Player Report": [
        ("What is your username?", discord.TextStyle.short),
        ("Who are you reporting?", discord.TextStyle.short),
        ("Why are you reporting them?", discord.TextStyle.paragraph)
    ],
    "Inventory Refund": [
        ("What is your username?", discord.TextStyle.short),
        ("On what server do you need a refund?", discord.TextStyle.short),
        ("Why do you need a refund?", discord.TextStyle.paragraph)
    ],
    "Punishment Appeal": [
        ("What is your username?", discord.TextStyle.short),
        ("On what server is your punishment?", discord.TextStyle.short),
        ("Why should we lift your punishment?", discord.TextStyle.paragraph)
    ],
    "Development Issue": [
        ("What is your username?", discord.TextStyle.short),
        ("On what server is the bug?", discord.TextStyle.short),
        ("What is the bug?", discord.TextStyle.paragraph)
    ],
    "Store Issue": [
        ("What is your username?", discord.TextStyle.short),
        ("On what server is your purchase?", discord.TextStyle.short),
        ("What is your issue?", discord.TextStyle.paragraph)
    ],
    "Staff Report": [
        ("What is your username?", discord.TextStyle.short),
        ("Who are you reporting?", discord.TextStyle.short),
        ("For what are you reporting them?", discord.TextStyle.paragraph)
    ]
}

STAFF_ROLE_NAME = "💻│Ticket Perms"
MANAGER_ROLE_NAME = "🤖│Ticket Admin Perms"

async def ensure_roles(guild: discord.Guild):
    staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
    if not staff_role:
        staff_role = await guild.create_role(name=STAFF_ROLE_NAME)

    manager_role = discord.utils.get(guild.roles, name=MANAGER_ROLE_NAME)
    if not manager_role:
        manager_role = await guild.create_role(name=MANAGER_ROLE_NAME)

    return staff_role, manager_role

class TicketModal(ui.Modal):
    def __init__(self, ticket_type):
        super().__init__(title=f"{ticket_type} Ticket")
        self.ticket_type = ticket_type
        self.inputs = []

        for label, style in MODAL_QUESTIONS[ticket_type]:
            input = ui.TextInput(label=label, style=style, required=True)
            self.inputs.append(input)
            self.add_item(input)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        ticket_type = self.ticket_type

        staff_role, _ = await ensure_roles(guild)

        category_name = TICKET_CATEGORIES[ticket_type]
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(name=category_name)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"{ticket_type.lower().replace(' ', '-')}-{user.name}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(title=f"{ticket_type} Ticket", color=discord.Color.blue())
        for field in self.inputs:
            embed.add_field(name=field.label, value=field.value, inline=False)

        embed.set_footer(text=f"User: {user} | ID: {user.id}")

        await interaction.response.send_message(f"✅ Your ticket has been created: {channel.mention}", ephemeral=True)

        await channel.send(
            content=f"{user.mention} {staff_role.mention}\n**Ticket Type:** {ticket_type}",
            embed=embed
        )

class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, description=f"Open a {label.lower()} ticket.")
            for label in TICKET_CATEGORIES
        ]
        super().__init__(placeholder="Select a ticket type...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.values[0]))

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await ensure_roles(guild)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s). Bot is ready.")
    except Exception as e:
        print(e)

@bot.tree.command(name="ticketpanel")
@app_commands.default_permissions(administrator=True)
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌛 Create a Ticket",
        description="Select the type of ticket you want to open from the dropdown below.",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, view=TicketView())

async def get_transcript(channel):
    messages = [
        f"[{msg.created_at}] {msg.author.display_name}: {msg.content}"
        async for msg in channel.history(limit=None, oldest_first=True)
        if not msg.author.bot
    ]
    return "\n".join(messages)

@bot.tree.command(name="closerequest")
async def closerequest(interaction: discord.Interaction, reason: str):
    staff_role, manager_role = await ensure_roles(interaction.guild)
    if not any(role in interaction.user.roles for role in [staff_role, manager_role]):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.response.send_message(f"{staff_role.mention} Close request: {reason}", ephemeral=False)

@bot.tree.command(name="close")
async def close(interaction: discord.Interaction, reason: str):
    staff_role, manager_role = await ensure_roles(interaction.guild)
    if not any(role in interaction.user.roles for role in [staff_role, manager_role]):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    transcript = await get_transcript(interaction.channel)
    transcript_channel = discord.utils.get(interaction.guild.text_channels, name=TRANSCRIPT_CHANNEL_NAME)
    if not transcript_channel:
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        transcript_channel = await interaction.guild.create_text_channel(TRANSCRIPT_CHANNEL_NAME, overwrites=overwrites)

    file = discord.File(io.StringIO(transcript), filename="transcript.txt")
    await transcript_channel.send(content=f"Transcript from {interaction.channel.name} | Closed for: {reason}", file=file)
    await interaction.channel.delete()

@bot.tree.command(name="rename")
async def rename(interaction: discord.Interaction, name: str):
    staff_role, manager_role = await ensure_roles(interaction.guild)
    if not any(role in interaction.user.roles for role in [staff_role, manager_role]):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.channel.edit(name=name)
    await interaction.response.send_message(f"Channel renamed to `{name}`.", ephemeral=True)

@bot.tree.command(name="move")
async def move(interaction: discord.Interaction, category: discord.CategoryChannel):
    _, manager_role = await ensure_roles(interaction.guild)
    if manager_role not in interaction.user.roles:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.channel.edit(category=category)
    await interaction.response.send_message(f"Channel moved to {category.name}.", ephemeral=True)

@bot.tree.command(name="add")
async def add(interaction: discord.Interaction, member: discord.Member):
    _, manager_role = await ensure_roles(interaction.guild)
    if manager_role not in interaction.user.roles:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
    await interaction.response.send_message(f"{member.mention} has been added to the ticket.", ephemeral=True)

@bot.tree.command(name="remove")
async def remove(interaction: discord.Interaction, member: discord.Member):
    _, manager_role = await ensure_roles(interaction.guild)
    if manager_role not in interaction.user.roles:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.channel.set_permissions(member, overwrite=None)
    await interaction.response.send_message(f"{member.mention} has been removed from the ticket.", ephemeral=True)
@bot.event
async def on_ready():
    for guild in bot.guilds:
        await ensure_roles(guild)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s). Bot is ready.")
    except Exception as e:
        print(e)
bot.run(TOKEN)