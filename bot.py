import discord
from discord.ext import commands
import requests
import sqlite3
from urllib.parse import quote

import os

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIXO = "!"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIXO, intents=intents)

# =========================
# BANCO DE DADOS
# =========================

conn = sqlite3.connect("guilda_monitor.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS membros (
    guilda TEXT,
    jogador TEXT,
    PRIMARY KEY (guilda, jogador)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS guildas (
    nome TEXT PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    guilda TEXT,
    jogador TEXT,
    level INTEGER,
    PRIMARY KEY (guilda, jogador)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    guilda TEXT,
    jogador TEXT,
    level INTEGER,
    PRIMARY KEY (guilda, jogador)
)
""")
conn.commit()
conn.close()

# =========================
# API
# =========================

def obter_dados_guilda(nome_guilda):
    url = f"https://rucoystatsapi.net/api/Guild/guild={quote(nome_guilda)}"

    try:
        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            return None

        return response.json()

    except:
        return None


def obter_membros(nome_guilda):

    data = obter_dados_guilda(nome_guilda)

    if not data:
        return []

    return [
        {
            "nome": p.get("name", "Desconhecido"),
            "level": p.get("level", 0)
        }
        for p in data.get("players", [])
    ]


def obter_online(nome_guilda):

    data = obter_dados_guilda(nome_guilda)

    if not data:
        return []

    online = []

    for player in data.get("players", []):

        status = str(
            player.get("lastOnline", "")
        ).lower()

        if "currently online" in status:

            online.append({
                "nome": player.get("name", "Desconhecido"),
                "level": player.get("level", 0)
            })

    return online


def verificar_alteracoes(nome_guilda):

    membros_atuais = {
        jogador["nome"]
        for jogador in obter_membros(nome_guilda)
    }

    conn = sqlite3.connect("guilda_monitor.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT jogador FROM membros WHERE guilda=?",
        (nome_guilda,)
    )

    membros_salvos = {
        row[0]
        for row in cursor.fetchall()
    }

    entrou = membros_atuais - membros_salvos
    saiu = membros_salvos - membros_atuais

    cursor.execute(
        "DELETE FROM membros WHERE guilda=?",
        (nome_guilda,)
    )

    for jogador in membros_atuais:
        cursor.execute(
            "INSERT OR IGNORE INTO membros VALUES (?, ?)",
            (nome_guilda, jogador)
        )

    conn.commit()
    conn.close()

    return entrou, saiu

# =========================
# EVENTOS
# =========================

@bot.event
async def on_ready():
    print(f"✅ Logado como {bot.user}")

# =========================
# COMANDOS
# =========================

@bot.command()
async def guilda(ctx, *, nome_guilda):

    membros = obter_membros(nome_guilda)

    if not membros:
        await ctx.send("❌ Guilda não encontrada.")
        return

    texto = (
        f"🛡️ {nome_guilda}\n"
        f"👥 Total: {len(membros)}\n\n"
    )

    for membro in membros[:100]:

        texto += (
            f"• {membro['nome']} "
            f"(Lv {membro['level']})\n"
        )

    await ctx.send(texto[:2000])


@bot.command()
async def online(ctx, *, nome_guilda):

    jogadores = obter_online(nome_guilda)

    if not jogadores:

        await ctx.send(
            f"🔴 Nenhum membro online em {nome_guilda}."
        )

        return

    texto = (
        f"🟢 Online em {nome_guilda}: "
        f"{len(jogadores)}\n\n"
    )

    for jogador in jogadores:

        texto += (
            f"• {jogador['nome']} "
            f"(Lv {jogador['level']})\n"
        )

    await ctx.send(texto[:2000])


@bot.command()
async def entrou(ctx, *, nome_guilda):

    entrou, _ = verificar_alteracoes(nome_guilda)

    if not entrou:
        await ctx.send(
            "📭 Nenhum membro entrou desde a última consulta."
        )
        return

    texto = f"➕ Entraram em {nome_guilda}:\n\n"

    texto += "\n".join(
        f"• {p}"
        for p in sorted(entrou)
    )

    await ctx.send(texto[:2000])


@bot.command()
async def saiu(ctx, *, nome_guilda):

    _, saiu = verificar_alteracoes(nome_guilda)

    if not saiu:
        await ctx.send(
            "📭 Nenhum membro saiu desde a última consulta."
        )
        return

    texto = f"➖ Saíram de {nome_guilda}:\n\n"

    texto += "\n".join(
        f"• {p}"
        for p in sorted(saiu)
    )

    await ctx.send(texto[:2000])


@bot.command()
async def adicionarguilda(ctx, *, nome_guilda):

    conn = sqlite3.connect("guilda_monitor.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO guildas(nome) VALUES (?)",
        (nome_guilda,)
    )

    conn.commit()
    conn.close()

    await ctx.send(
        f"✅ Guilda {nome_guilda} adicionada."
    )


@bot.command()
async def removerguilda(ctx, *, nome_guilda):

    conn = sqlite3.connect("guilda_monitor.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM guildas WHERE nome=?",
        (nome_guilda,)
    )

    conn.commit()
    conn.close()

    await ctx.send(
        f"🗑️ Guilda {nome_guilda} removida."
    )


@bot.command()
async def guildas(ctx):

    conn = sqlite3.connect("guilda_monitor.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT nome FROM guildas ORDER BY nome"
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:
        await ctx.send(
            "📭 Nenhuma guilda cadastrada."
        )
        return

    texto = "📜 Guildas cadastradas:\n\n"

    texto += "\n".join(
        f"• {r[0]}"
        for r in rows
    )

    await ctx.send(texto[:2000])


@bot.command()
async def online_todas(ctx):

    conn = sqlite3.connect("guilda_monitor.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT nome FROM guildas"
    )

    guildas_salvas = [
        r[0]
        for r in cursor.fetchall()
    ]

    conn.close()

    if not guildas_salvas:
        await ctx.send(
            "📭 Nenhuma guilda cadastrada."
        )
        return

    resposta = ""

    for guilda in guildas_salvas:

        online = obter_online(guilda)

        resposta += (
            f"\n🛡️ {guilda}: "
            f"{len(online)} online\n"
        )

        for jogador in online[:10]:

            resposta += (
                f"• {jogador['nome']} "
                f"(Lv {jogador['level']})\n"
            )

    await ctx.send(resposta[:2000])
@bot.command()
async def jogador(ctx, *, nome_guilda):

    data = obter_dados_guilda(nome_guilda)

    if not data:
        await ctx.send("Erro")
        return

    player = data["players"][0]

    await ctx.send(f"```{player}```")
# =========================
# INICIAR BOT
# =========================
@bot.command()
async def regrediu(ctx, *, nome_guilda):

    data = obter_dados_guilda(nome_guilda)

    if not data:
        await ctx.send("❌ Guilda não encontrada.")
        return

    conn = sqlite3.connect("guilda_monitor.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS levels (
        guilda TEXT,
        jogador TEXT,
        level INTEGER,
        PRIMARY KEY (guilda, jogador)
    )
    """)

    regressos = []

    for player in data.get("players", []):

        nome = player.get("name")
        level_atual = player.get("level", 0)

        cursor.execute(
            """
            SELECT level
            FROM levels
            WHERE guilda=? AND jogador=?
            """,
            (nome_guilda, nome)
        )

        row = cursor.fetchone()

        if row:

            level_antigo = row[0]

            if level_atual < level_antigo:

                regressos.append(
                    (
                        nome,
                        level_antigo,
                        level_atual
                    )
                )

        cursor.execute(
            """
            INSERT OR REPLACE INTO levels
            VALUES (?, ?, ?)
            """,
            (
                nome_guilda,
                nome,
                level_atual
            )
        )

    conn.commit()
    conn.close()

    if not regressos:

        await ctx.send(
            f"✅ Nenhum jogador regrediu level em {nome_guilda}."
        )

        return

    texto = (
        f"⬇️ Jogadores que regrediram em "
        f"{nome_guilda}\n\n"
    )

    for nome, antigo, atual in regressos:

        texto += (
            f"• {nome}: "
            f"{antigo} ➜ {atual}\n"
        )

    await ctx.send(texto[:2000])
import os 
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("Erro: O token não foi configurado corretamente no Railway.")
else:
    bot.run(TOKEN)