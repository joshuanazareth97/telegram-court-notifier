import json
import os
import time
import requests
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes, CommandHandler, CallbackContext
from dotenv import load_dotenv

import asyncio

#### CONFIG ####
load_dotenv()
BOT_TOKEN = os.getenv("SC_TELEGRAM_BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

API_URL = "https://registry.sci.gov.in/ca_iscdb/index.php?courtListCsv=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,21,22&request=display_full&requestType=ajax"
# polling_interval = 60
polling_interval = 3

#### MEMORY STORE ####

# this has a mapping of case number to chat_ids that want to monitor that case
case_monitor = {}
users = []

# notify when failing repeatedly
failed_attempts = 0
FAIL_THRESHOLD = 15


async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in users:
        users.append(chat_id)

    case_nos = context.args[1:]
    court_no = context.args[0]
    if not court_no or not court_no[0] == "C":
        await context.bot.send_message(chat_id=chat_id, text="Provide court number")
    elif not case_nos:
        await context.bot.send_message(chat_id=chat_id, text="Provide case numbers")
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


def process_sc_api_result(data) -> list:
    # this returns a list of dictionaries with:
    # case metadata, case number , court number
    court_list = data["listedItemDetails"]
    case_list = []

    for court in court_list:
        status = court.get("item_status", "")
        if status != "HEARING":
            continue
        name = court.get("court_name", "")
        case_no = court.get("item_no", "")
        respondent_name = court.get("respondent_name", "")
        petitioner_name = court.get("petitioner_name", "")
        reg_no = court.get("registration_number_display", "")
        case_list.append(
            {
                "status": status,
                "court_name": name,
                "respondent_name": respondent_name,
                "petitioner_name": petitioner_name,
                "case_no": case_no,
                "reg_no": reg_no,
            }
        )

    return case_list


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
    # <Case Name>
    # <Case Number> now listed in <Court No>
    first_line = (
        f"{case['reg_no']} ({case['petitioner_name']} v. {case['respondent_name']})\n"
    )
    to_display = case["reg_no"] and case["respondent_name"] and case["petitioner_name"]
    second_line = (
        f"Case No. {case['case_no']} : Now listed in Court {case['court_name']}"
    )
    return f"{first_line if to_display else ''}{second_line}"


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
    listed_cases = process_sc_api_result(result.json())
    if not len(listed_cases):
        print("No cases found yet...")
    for case in listed_cases:
        if case["court_name"] not in case_monitor:
            continue
        court_monitor = case_monitor[case["court_name"]]
        chat_ids = court_monitor.get(case["case_no"], [])
        if chat_ids:
            print("Case Match!")
        for id in chat_ids:
            await context.bot.send_message(chat_id=id, text=format_message(case))
            clear_case(court_no=case["court_name"], case_number=case["case_no"])


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
    application.job_queue.run_repeating(check_for_cases, interval=30)
    # on different commands - answer in Telegram
    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(CommandHandler(["watch", "monitor"], handle_message))
    application.add_handler(CommandHandler(["status"], status))
    application.add_handler(CommandHandler(["clear"], clear))
    # Run the bot until the user presses Ctrl-C
    application.run_polling()


# if __name__ is "__main__":
main()
