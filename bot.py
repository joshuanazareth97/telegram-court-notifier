import os
import time
import requests
from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler
from dotenv import load_dotenv

import asyncio

dummy = [
  {
            "court_no": "1",
            "court_name": "C1",
            "item_no": "23",
            "registration_number_display": "",
            "petitioner_name": "",
            "respondent_name": "",
            "bg_class": " bg-alice ",
            "item_status": "HEARING",
            "court_message": ""
        },
        {
            "court_no": "2",
            "court_name": "C2",
            "item_no": "2",
            "registration_number_display": "SLP(Crl) No. 6555/2019",
            "petitioner_name": "kalyan kumar dubey ",
            "respondent_name": " the state of bihar",
            "bg_class": " bg-alice ",
            "item_status": "HEARING",
            "court_message": ""
        },
        {
            "court_no": "3",
            "court_name": "C3",
            "item_no": "4",
            "registration_number_display": "SLP(Crl) No. 1254/2023",
            "petitioner_name": "abhijit mandal ",
            "respondent_name": " the state of west bengal",
            "bg_class": " bg-alice ",
            "item_status": "HEARING",
            "court_message": "ITEM NOS.47 AND 49 WILL BE TAKEN AFTER ITEM NO. 32"
        }
]

#### CONFIG ####
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

API_URL = 'https://registry.sci.gov.in/ca_iscdb/index.php?courtListCsv=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,21,22&request=display_full&requestType=ajax'
# polling_interval = 60
polling_interval = 3

#### MEMORY STORE ####

# this has a mapping of case number to chat_ids that want to monitor that case
case_monitor = {}

users = []

# notify when failing repeatedly
failed_attempts = 0
FAIL_THRESHOLD = 15

def handle_message(update, context):
    chat_id = update.message.chat_id
    if chat_id not in users:
      users.append(chat_id)

    message_text = update.message.text

    case_nos = message_text.split(",")

    save_config(case_numbers=case_nos, chat_id=chat_id)

    bot.send_message(chat_id=chat_id, text=f'You are now monitoring: \n{case_nos.join(", ")}')

def save_config(case_numbers: list, chat_id: str):
    # Check memory and add me to the list of watchers for these cases if I am not present
  for case in case_numbers:
    current_watchers = case_monitor.get(case, [])
    if chat_id in current_watchers:
      continue
    case_monitor[case] = current_watchers + [chat_id]
  # persist case_monitor
  pass

def retrieve_config(chat_id: str):
  # save in memory for fast retrieval
  pass

def process_api_result(data) -> list:
  # this returns a list of dictionaries with:
  # case metadata, case number , court number
  court_list = data["listedItemDetails"]
  case_list = []

  for court in court_list:
    status = court.get("item_status", "")
    if status != "HEARING": continue
    name = court.get("court_name", "")
    case_no = court.get("item_no", "")
    respondent_name = court.get("respondent_name", "")
    petitioner_name = court.get("petitioner_name", "")
    reg_no = court.get("registration_number_display", "")
    case_list.append({
      "status": status,
      "court_name": name,
      "respondent_name": respondent_name,
      "petitioner_name": petitioner_name,
      "case_no": case_no,
      "reg_no": reg_no
    })

  return case_list

def poll_api():
  response = requests.get(API_URL)

  if response.ok:
    failed_attempts = 0
    return response

  failed_attempts += 1
  if failed_attempts > FAIL_THRESHOLD:
    for user in users:
      bot.send_message(chat_id=user, text=f"Data retrieval has failed over the past {FAIL_THRESHOLD} mins. Please contact Joshua to resolve this.")
      return None



def format_message(case: dict) -> str:
  # takes in a case dict and returns a formatted string
  # <Case Name>
  # <Case Number> now listed in <Court No>
  first_line = f"{case['reg_no']} ({case['petitioner_name']} v. {case['respondent_name']})\n"
  to_display = case['reg_no'] and case['respondent_name'] and case['petitioner_name']
  second_line=f"Case No. {case['case_no']} : Now listed in Court {case['court_name']}"
  return f"{first_line if to_display else ''}{second_line}"

def clear_case(case_number: str):
  case_monitor.pop(case_number)
  pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I can notify you when cases get listed. Send me a message with /monitor  ")

async def main():
  # TODO: Find the recced way oof exiting a script like this
  print("Telegram Case Listing Bot is running...")

  while True:
    time.sleep(10)
    result = poll_api()
    if not result: continue
    listed_cases = process_api_result(result.json())
    if not len(listed_cases):
      print("No cases found yet...")
    for case in listed_cases:
      if case["case_no"] not in case_monitor:
        continue
      chat_ids = case_monitor.get(case["number"], [])
      for id in chat_ids:
        bot.send_message(chat_id=id, message=format_message(case))
      clear_case(case_number=case["case_no"])

    print("\n+++++++++\n")

if __name__ is "__main__":
  asyncio.run(main())

