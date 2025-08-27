from keep_alive import keep_alive
keep_alive()
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random
import threading
import time
import os

TOKEN = os.getenv("TOKEN")

# Game state dictionaries, keyed by chat_id
games = {}  # Stores all game data: {chat_id: {"players": {}, "positions": {}, ...}}
MAX_PLAYERS = 4
snakes = {17: 7, 54: 34, 62: 19, 64: 60, 87: 24, 93: 73, 95: 75, 98: 79}
ladders = {3: 22, 5: 8, 11: 26, 20: 29, 27: 56, 21: 82, 72: 91, 80: 99}

def init_game_state():
    """Initialize game state for a chat."""
    return {
        "players": {},
        "positions": {},
        "entered_board": {},
        "game_started": False,
        "turn": None,
        "reverse_mode": {},
        "reverse_ready": {},
        "winners": {},
        "creation_time": None,
        "timeout_timer": None,
        "timeout_seconds": 120  # 2 minutes
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Welcome to Snake & Ladder Bot!\n\n"
        "/join – Join game (max 4)\n"
        "/startgame – Start (min 2 players)\n"
        "/play – Roll dice on your turn\n"
        "/score – View leaderboard\n"
        "/end – End current game\n"
        "/help – Show instructions"
    )

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user = update.message.from_user

    # Initialize game state for this chat if it doesn't exist
    if chat_id not in games:
        games[chat_id] = init_game_state()

    game = games[chat_id]
    if game["game_started"]:
        await update.message.reply_text("🚫 Game already started!")
        return
    if user.id in game["players"]:
        await update.message.reply_text("You're already in!")
        return
    if len(game["players"]) >= MAX_PLAYERS:
        await update.message.reply_text("Only 4 players allowed at a time!")
        return

    game["players"][user.id] = user.first_name
    game["positions"][user.id] = 0
    game["entered_board"][user.id] = False
    game["reverse_mode"][user.id] = False
    game["reverse_ready"][user.id] = False
    await update.message.reply_text(f"✅ {user.first_name} joined the game!")

    # If this is the first player, start the timeout
    if len(game["players"]) == 1:
        game["creation_time"] = time.time()
        game["timeout_timer"] = threading.Timer(game["timeout_seconds"], lambda: check_timeout(chat_id, context))
        game["timeout_timer"].start()
        await update.message.reply_text("⏳ Waiting for more players. Game will end in 2 minutes if not started.")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in games:
        await update.message.reply_text("❗ No game running. Use /join to start.")
        return

    game = games[chat_id]
    if len(game["players"]) < 2:
        await update.message.reply_text("❗ At least 2 players needed to start.")
        return
    game["game_started"] = True
    # Cancel the timeout timer since the game is starting
    if game["timeout_timer"] is not None:
        game["timeout_timer"].cancel()
        game["timeout_timer"] = None
    game["turn"] = list(game["players"].keys())[0]
    await update.message.reply_text(f"🎮 Game started!\n🎯 First turn: {game['players'][game['turn']]}")

def check_timeout(chat_id, context):
    if chat_id not in games:
        return
    game = games[chat_id]
    if not game["game_started"] and len(game["players"]) > 0:
        reset_game(chat_id)
        context.bot.send_message(chat_id=chat_id, text="🛑 Game ended due to inactivity (2 minutes passed without starting).")
        print(f"Game in chat {chat_id} timed out and reset.")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user = update.message.from_user
    if chat_id not in games:
        await update.message.reply_text("❗ No game running. Use /join to start.")
        return

    game = games[chat_id]
    if not game["game_started"]:
        await update.message.reply_text("❗ Game not started. Use /startgame.")
        return
    if user.id != game["turn"]:
        await update.message.reply_text("⏳ Wait for your turn!")
        return

    dice = random.randint(1, 6)
    msg = f"🎲 {game['players'][user.id]} rolled a {dice}!\n"

    if not game["entered_board"][user.id]:
        if dice == 1:
            game["entered_board"][user.id] = True
            game["positions"][user.id] = 1
            msg += "🎉 Entered the board at position 1!\n"
        else:
            msg += "❗ You need a 1 to enter the board.\n"
            await update.message.reply_text(msg)
            await next_turn(chat_id, user.id, update)
            return
    elif not game["reverse_mode"][user.id]:
        pos = game["positions"][user.id]
        new_pos = pos + dice
        if new_pos > 100:
            msg += f"🚫 Need exact {100 - pos} to reach 100. No move.\n"
        elif new_pos == 100:
            game["reverse_mode"][user.id] = True
            msg += f"🎯 Reached 100! Now roll a 6 to begin returning to 1.\n"
            game["positions"][user.id] = 100
        else:
            game["positions"][user.id] = new_pos
            msg += f"➡️ Moved to {game['positions'][user.id]}\n"
            msg += apply_snakes_and_ladders(chat_id, user.id)
    else:
        if not game["reverse_ready"][user.id]:
            if dice == 6:
                game["reverse_ready"][user.id] = True
                msg += "✅ Rolled a 6! Start moving toward 1.\n"
            else:
                msg += "❗ Need a 6 to begin reverse journey.\n"
                await update.message.reply_text(msg)
                await next_turn(chat_id, user.id, update)
                return
        else:
            new_pos = game["positions"][user.id] - dice
            if new_pos < 1:
                msg += f"🚫 Need exact {game['positions'][user.id] - 1} to reach 1. No move.\n"
            elif new_pos == 1:
                game["winners"][user.id] = game["winners"].get(user.id, 0) + 1
                msg += f"🏆 {game['players'][user.id]} wins the game!\n"
                await update.message.reply_text(msg)
                reset_game(chat_id)
                return
            else:
                game["positions"][user.id] = new_pos
                msg += f"⬅️ Moved back to {game['positions'][user.id]}\n"
                msg += apply_snakes_and_ladders(chat_id, user.id)

    await update.message.reply_text(msg)
    await next_turn(chat_id, user.id, update)

def apply_snakes_and_ladders(chat_id, user_id):
    game = games[chat_id]
    msg = ""
    pos = game["positions"][user_id]
    if pos in snakes:
        game["positions"][user_id] = snakes[pos]
        msg += f"🐍 Snake! Down to {game['positions'][user_id]}\n"
    elif pos in ladders:
        game["positions"][user_id] = ladders[pos]
        msg += f"🪜 Ladder! Up to {game['positions'][user_id]}\n"
    return msg

async def next_turn(chat_id, current_uid, update):
    game = games[chat_id]
    keys = list(game["players"].keys())
    next_index = (keys.index(current_uid) + 1) % len(keys)
    game["turn"] = keys[next_index]
    await update.message.reply_text(f"👉 Next turn: {game['players'][game['turn']]}")

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in games or (not games[chat_id]["game_started"] and len(games[chat_id]["players"]) == 0):
        await update.message.reply_text("⚠️ No game is running.")
        return
    reset_game(chat_id)
    await update.message.reply_text("🛑 Game has been ended.")

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in games or not games[chat_id]["winners"]:
        await update.message.reply_text("📭 No winners yet.")
        return
    game = games[chat_id]
    leaderboard = sorted(game["winners"].items(), key=lambda x: x[1], reverse=True)
    msg = "🏅 Scoreboard:\n"
    for uid, score in leaderboard:
        msg += f"{game['players'].get(uid, 'Unknown')} – {score} wins\n"
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def reset_game(chat_id):
    if chat_id in games:
        game = games[chat_id]
        if game["timeout_timer"] is not None:
            game["timeout_timer"].cancel()
        games[chat_id] = init_game_state()

# Run the bot
app = ApplicationBuilder().token(TOKEN).read_timeout(30).write_timeout(30).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("join", join))
app.add_handler(CommandHandler("startgame", start_game))
app.add_handler(CommandHandler("play", play))
app.add_handler(CommandHandler("score", score))
app.add_handler(CommandHandler("end", end))
app.add_handler(CommandHandler("help", help_command))

print("✅ Bot running...")
app.run_polling()
