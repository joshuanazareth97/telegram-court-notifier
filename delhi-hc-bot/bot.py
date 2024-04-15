import json
import os
import requests
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes, CommandHandler, CallbackContext
from dotenv import load_dotenv
import re
from bs4 import BeautifulSoup

#### CONFIG ####
load_dotenv()
BOT_TOKEN = os.getenv("DHC_TELEGRAM_BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

API_URL = "https://delhihighcourt.nic.in/display_board"

polling_interval = 30

#### MEMORY STORE ####

# this has a mapping of case number to chat_ids that want to monitor that case
case_monitor = {}
users = []

# notify when failing repeatedly
failed_attempts = 0
FAIL_THRESHOLD = 15


async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not context.args:
        await context.bot.send_message(
            chat_id=chat_id, text="Provide court number and case number(s)"
        )
        return
    if chat_id not in users:
        users.append(chat_id)

    case_nos = context.args[1:]
    court_no = context.args[0]
    if not court_no or not re.search("\d+", court_no):
        await context.bot.send_message(chat_id=chat_id, text="Provide court number")
    elif not case_nos or not all([re.search("[A-Za-z]\d+", case) for case in case_nos]):
        await context.bot.send_message(chat_id=chat_id, text="Provide case number(s)")
    else:
        save_config(court_no=court_no, case_numbers=case_nos, chat_id=chat_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f'You are now monitoring items: \n{", ".join(case_nos)} in {court_no}',
        )


def save_config(court_no: str, case_numbers: list, chat_id: str):
    # Check memory and add me to the list of watchers for these cases if I am not present
    court_monitor = case_monitor.get(court_no, {})
    for case in case_numbers:
        current_watchers = court_monitor.get(case, [])
        if chat_id in current_watchers:
            continue
        court_monitor[case] = current_watchers + [chat_id]
        case_monitor[court_no] = court_monitor
        # persist case_monitor
        with open("monitor.db.json", "w") as f:
            json.dump(case_monitor, f)


def retrieve_config():
    with open("monitor.db.json", "r") as f:
        json_object = json.load(f)
        for key in json_object:
            case_monitor[key] = json_object[key]


def process_delhi_hc_api_result(html) -> list:
    # this returns a list of dictionaries with:
    # case metadata, case number , court number
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="table table-bordered table-hover table-striped")
    headers = [header.text.strip().lower() for header in table.find_all("th")]

    data_list = []
    # skip the first row as it contains headers
    rows = table.find_all("tr")[1:]

    for row in rows:
        row_data = {}
        cells = row.find_all("td")
        in_session = True
        for index, cell in enumerate(cells):
            # is this a court cell, or a case cell?
            if cell_data := cell.find("a"):
                cell_text = cell_data.text.strip()
                row_data[headers[index]] = cell_text
                row_data["url"] = cell_data["href"]
            else:
                cell_data = cell.text.strip()
                if cell_data == 'Not in Session':
                    in_session = False
                    continue
                row_data[headers[index]] = cell_data.split(" ")[0]
        if in_session: data_list.append(row_data)

    return data_list


def poll_api(bot: Bot):
    response = requests.get(API_URL)

    if response.ok:
        failed_attempts = 0
        return response

    failed_attempts += 1
    if failed_attempts > FAIL_THRESHOLD:
        for user in users:
            bot.send_message(
                chat_id=user,
                text=f"Data retrieval has failed over the past {FAIL_THRESHOLD} attempts. Please contact Joshua to resolve this.",
            )
            return None


def format_message(case: dict) -> str:
    # takes in a case dict and returns a formatted string
    # <Case Number> now listed in <Court No>
    return f"Court {case['court']}: Now hearing Case No. {case['item']}"


def clear_case(court_no: str, case_number: str):
    case_monitor[court_no].pop(case_number)
    with open("monitor.db.json", "w") as f:
        json.dump(case_monitor, f)
    pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I can notify you when cases get listed. Send me a message with /monitor <Court Name> <Court Case 1> <Court Case 2> ...  ",
    )


async def check_for_cases(context: CallbackContext):
    result = poll_api(bot=context.bot)
    if not result:
        return None
    listed_cases = process_delhi_hc_api_result(result.text)
    if not len(listed_cases):
        print("No cases found yet...")
    for case in listed_cases:
        if case["court"] not in case_monitor:
            continue
        court_monitor = case_monitor[case["court"]]
        case_no = case["item"]
        if not case_no:
            continue
        chat_ids = court_monitor.get(case_no, [])
        if chat_ids:
            print("Case Match!")
        for id in chat_ids:
            await context.bot.send_message(chat_id=id, text=format_message(case))
            clear_case(court_no=case["court"], case_number=case["item"])


def format_status(chat_id: str):
    """Pretty prints the status_monitor dictionary"""
    return "\n".join(
        [
            f"{court_no}: {', '.join(case_monitor[court_no].keys())}"
            for court_no in case_monitor
        ]
        + [f"\nTotal cases monitored: {len(case_monitor)}"]
        + [f"\nCurrent chat_id: {chat_id}"]
    )


async def status(update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message with the current cases being monitored"""
    if await check_admin_password(update, context):
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=format_status(chat_id=update.message.chat_id),
        )


async def clear(update, context: ContextTypes.DEFAULT_TYPE):
    """Clears the current case_monitor dictionary"""
    if await check_admin_password(update, context):
        case_monitor.clear()
        with open("monitor.db.json", "w") as f:
            json.dump(case_monitor, f)
        await context.bot.send_message(
            chat_id=update.message.chat_id, text="Case monitor cleared."
        )


async def check_admin_password(update, context: ContextTypes.DEFAULT_TYPE):
    """Checks if the admin password is correct"""
    if context.args and context.args[0] == ADMIN_PASSWORD:
        return True
    else:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="You are not authorized to perform this action.",
        )
        return False


def main():
    # TODO: Find the recced way oof exiting a script like this
    """Run bot."""
    print("Telegram Case Listing Bot is running...")
    try:
        retrieve_config()
        print(case_monitor)
    except FileNotFoundError:
        pass
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()
    application.job_queue.run_repeating(check_for_cases, interval=polling_interval)
    # on different commands - answer in Telegram
    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(CommandHandler(["watch", "monitor"], handle_message))
    application.add_handler(CommandHandler(["status"], status))
    application.add_handler(CommandHandler(["clear"], clear))
    # Run the bot until the user presses Ctrl-C
    application.run_polling()


# if __name__ is "__main__":
main()
