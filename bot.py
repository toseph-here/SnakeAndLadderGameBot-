from keep_alive import keep_alive
keep_alive()
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random

import os
TOKEN = os.getenv("TOKEN")
players = {}
positions = {}
entered_board = {}
game_started = False
turn = None
reverse_mode = {}
reverse_ready = {}
winners = {}
MAX_PLAYERS = 4

snakes = {17: 7, 54: 34, 62: 19, 64: 60, 87: 24, 93: 73, 95: 75, 98: 79}
ladders = {3: 22, 5: 8, 11: 26, 20: 29, 27: 56, 21: 82, 72: 91, 80: 99}

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
    global players
    user = update.message.from_user
    if game_started:
        await update.message.reply_text("🚫 Game already started!")
        return
    if user.id in players:
        await update.message.reply_text("You're already in!")
        return
    if len(players) >= MAX_PLAYERS:
        await update.message.reply_text("Only 4 players allowed at a time!")
        return

    players[user.id] = user.first_name
    positions[user.id] = 0
    entered_board[user.id] = False
    reverse_mode[user.id] = False
    reverse_ready[user.id] = False
    await update.message.reply_text(f"✅ {user.first_name} joined the game!")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_started, turn
    if len(players) < 2:
        await update.message.reply_text("❗At least 2 players needed to start.")
        return
    game_started = True
    turn = list(players.keys())[0]
    await update.message.reply_text(f"🎮 Game started!\n🎯 First turn: {players[turn]}")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global turn
    user = update.message.from_user
    if not game_started:
        await update.message.reply_text("❗Game not started. Use /startgame.")
        return
    if user.id != turn:
        await update.message.reply_text("⏳ Wait for your turn!")
        return

    dice = random.randint(1, 6)
    msg = f"🎲 {players[user.id]} rolled a {dice}!\n"

    if not entered_board[user.id]:
        if dice == 1:
            entered_board[user.id] = True
            positions[user.id] = 1
            msg += "🎉 Entered the board at position 1!\n"
        else:
            msg += "❗ You need a 1 to enter the board.\n"
            await update.message.reply_text(msg)
            await next_turn(user.id, update)
            return

    elif not reverse_mode[user.id]:
        pos = positions[user.id]
        new_pos = pos + dice
        if new_pos > 100:
            msg += f"🚫 Need exact {100 - pos} to reach 100. No move.\n"
        elif new_pos == 100:
            reverse_mode[user.id] = True
            msg += f"🎯 Reached 100! Now roll a 6 to begin returning to 1.\n"
            positions[user.id] = 100
        else:
            positions[user.id] = new_pos
            msg += f"➡️ Moved to {positions[user.id]}\n"
            msg += apply_snakes_and_ladders(user.id)
    else:
        if not reverse_ready[user.id]:
            if dice == 6:
                reverse_ready[user.id] = True
                msg += "✅ Rolled a 6! Start moving toward 1.\n"
            else:
                msg += "❗ Need a 6 to begin reverse journey.\n"
                await update.message.reply_text(msg)
                await next_turn(user.id, update)
                return
        else:
            new_pos = positions[user.id] - dice
            if new_pos < 1:
                msg += f"🚫 Need exact {positions[user.id] - 1} to reach 1. No move.\n"
            elif new_pos == 1:
                winners[user.id] = winners.get(user.id, 0) + 1
                msg += f"🏆 {players[user.id]} wins the game!\n"
                await update.message.reply_text(msg)
                reset_game()
                return
            else:
                positions[user.id] = new_pos
                msg += f"⬅️ Moved back to {positions[user.id]}\n"
                msg += apply_snakes_and_ladders(user.id)

    await update.message.reply_text(msg)
    await next_turn(user.id, update)

def apply_snakes_and_ladders(user_id):
    msg = ""
    pos = positions[user_id]
    if pos in snakes:
        positions[user_id] = snakes[pos]
        msg += f"🐍 Snake! Down to {positions[user_id]}\n"
    elif pos in ladders:
        positions[user_id] = ladders[pos]
        msg += f"🪜 Ladder! Up to {positions[user_id]}\n"
    return msg

async def next_turn(current_uid, update):
    global turn
    keys = list(players.keys())
    next_index = (keys.index(current_uid) + 1) % len(players)
    turn = keys[next_index]
    await update.message.reply_text(f"👉 Next turn: {players[turn]}")

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_started:
        await update.message.reply_text("⚠️ Game is not running.")
        return
    reset_game()
    await update.message.reply_text("🛑 Game has been ended.")

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not winners:
        await update.message.reply_text("📭 No winners yet.")
        return
    leaderboard = sorted(winners.items(), key=lambda x: x[1], reverse=True)
    msg = "🏅 Scoreboard:\n"
    for uid, score in leaderboard:
        msg += f"{players.get(uid, 'Unknown')} – {score} wins\n"
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def reset_game():
    global players, positions, entered_board, game_started, turn, reverse_mode, reverse_ready
    positions = {}
    entered_board = {}
    reverse_mode = {}
    reverse_ready = {}
    turn = None
    players = {}
    game_started = False

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
