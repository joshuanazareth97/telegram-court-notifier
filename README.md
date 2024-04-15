# Court Case Monitor

This is a set of Python scripts that monitor court cases listed in either the Supreme Court of India or Delhi High Court and sends a message to Telegram if there are any updates. It is based on the Telegram Bot API.

## Usage
Installation instructions and commands for each script are given in the README files present within the script's respective directory.

- [Supreme Court of India]( sc-bot/README.md )
- [Delhi High Court]( delhi-hc-bot/README.md )

## License
This code is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Todo:

- To stop monitoring a case, you can send the following message: `/stop_monitoring <court_no> <case_no>`

- Persist case monitor data to DB instead of regular file.