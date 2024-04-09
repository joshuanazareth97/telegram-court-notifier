## Installation

To use this script, you need to install some Python libraries:

- requests
- python-dotenv
- python-telegram-bot

You can install them by running:

```
pip install requests python-dotenv python-telegram-bot
```

You will also need to obtain a Telegram Bot API token by following the instructions [here](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).

## Configuration

Copy the `.env.example` file to `.env` and set the value of `SC_TELEGRAM_BOT_TOKEN` to the token you obtained from BotFather.

Next, run the script:

```
python court_case_monitor.py
```

## Usage

You can use this script to monitor cases from the SCI. To monitor a case, you need to provide the court number and case number.

Send the following message to the bot to start monitoring a case:

```
/monitor <court_no> <case_no_1> <case_no_2> ...
```

For example:

```
/monitor C12 1 2 3
```

The bot will send you a message when any of the cases in the specified court you are monitoring are updated.

## Todo:

- To stop monitoring a case, you can send the following message:

```
/stop_monitoring <court_no> <case_no>
```

