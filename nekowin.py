#!./bin/python
from logging import debug
from flask import Flask, jsonify
from dotenv import load_dotenv
from flask import json
from flask.json import load
import requests
import os
import time
import threading

from src.new_wallet import new_wallet
from src.util import *

load_dotenv()

WALLET_API = os.environ.get('WALLET_API') or 'http://127.0.0.1:8090/v2/'
# interval to payout the pot in seconds
SWEEP_INTERVAL = int(os.environ.get('SWEEP_INTERVAL') or (10))

PASSPHRASE = os.environ.get('PASSPHRASE')  # transaction passphrase

FEE_ADDRESS = os.environ.get('FEE_ADDRESS')  # where to send collected fees
FEE = 0.05  # amount of fee that is taken from the jackpot payout

LISTEN_PORT = os.environ.get('LISTEN_PORT') or 80

lottery_details = {}  # contains details about the current lottery taking place
wallet_id = ''  # contains the workign wallet id

app = Flask('nekowin')
last_sweep = now()
holdovers = dict()
last_winner = ''
# Flask api lottery amount


@app.route("/lottery")
def lottery():
    lottery_details['balance'] = 0
    lottery_details['trans_fees'] = 0
    try:
        if (os.environ.get('NETWORK') == 'TESTNET'):
            values = calc_pot(WALLET_API, wallet_id, FEE,
                              'addr_test1qrr2g5t4w540n5ttgk6qdewrycsu60ephyvtmawy04s9ng3d45nklzxerg5096eaaj240708fa2n7uev5hrxvlrm8c9sa2t0kj')
        else:
            values = calc_pot(WALLET_API, wallet_id, FEE)
        values[0] = max(values[0], 0)
        lottery_details['balance'] = values[2]
        lottery_details['trans_fees'] = values[3]

    except RuntimeError:
        values = [0, 1000000]

    global holdovers
    global last_sweep
    lottery_details['jackpot'] = values[0]
    lottery_details['fee'] = values[1]
    print(holdovers)
    temp_dict = dict()
    temp_dict.update(entries(WALLET_API, wallet_id, last_sweep))
    temp_dict.update(holdovers)
    lottery_details['entries'] = temp_dict
    lottery_details['last_winner'] = last_winner

    return jsonify(lottery_details)

# Forks flask to run in the background


def forkFlask():
    print("API Listening at http://localhost:" + str(LISTEN_PORT))
    return threading.Thread(target=lambda: app.run(host="0.0.0.0", port=LISTEN_PORT, debug=False, use_reloader=False)).start()


def record(filename, to_write):
    try:
        fd = os.open('logs/' + filename, os.O_WRONLY | os.O_TRUNC | os.O_CREAT)
        os.write(fd, str.encode(str(to_write)))
        os.close(fd)
    except Exception as e:
        print('Failed to record ' + str(filename))
        print(e)


def init():
    global wallet_id
    # query wallets available
    try:
        wallets = requests.get(WALLET_API + 'wallets').json()
    except requests.RequestException as e:
        print('Failed to list wallets. Ensure wallet is running and URI is correct')
        print(str(e))
        exit(-1)

    if len(wallets) > 0:
        wallet_id = wallets[0]['id']
    else:
        wallet_id = new_wallet(WALLET_API, PASSPHRASE)
        exit(0)

    print('Using wallet with id ' + str(wallet_id))

    # check for existing pot address in config if not create it
    #pot_address = create_address(WALLET_API)
    #print('Using pot address ' +  pot_address)

    return wallet_id


def start(wallet_id: str):
    """ Begin running neko win using the provided wallet """
    global last_sweep
    global last_winner
    last_sweep = now()
    global holdovers  # used to hold entries for a skipped lottery
    holdovers = dict()

    print('\nStarting Neko.Win')
    forkFlask()

    while True:
        print('\nNew lottery! Starting time ' + str(last_sweep))
        print('Waiting ' + str(SWEEP_INTERVAL) + 's for entrants')

        # Update lottery details for site clients
        lottery_details['start'] = last_sweep
        lottery_details['duration'] = SWEEP_INTERVAL

        # Sleep for Sweep interval
        time.sleep(SWEEP_INTERVAL)

        # Save the sweep time for record keeping
        last_last_sweep = last_sweep

        # Get all entries since last_sweep
        lottery_entries = entries(WALLET_API, wallet_id, last_sweep)
        lottery_entries.update(holdovers)

        # Set last_sweep to now
        last_sweep = now()

        # Log the entrants incase of refunding, etc
        record(str(last_last_sweep) + "_entries", lottery_entries)

        # If there are no entries, do not draw a winner
        if len(lottery_entries) <= 0:
            print('No one entered the lottery :(')
            continue
        else:
            print('Drawing from ' + str(len(lottery_entries)) + ' entries')

        # Randomly choose winner and payout to their address
        winner_address = draw_winner(lottery_entries)
        print(str(winner_address) + ' was drawn as the winner!')
        #pot_amount = calc_pot(WALLET_API, wallet_id, FEE)
        if (os.environ.get('NETWORK') == 'TESTNET'):
            values = calc_pot(WALLET_API, wallet_id, FEE,
                              'addr_test1qrr2g5t4w540n5ttgk6qdewrycsu60ephyvtmawy04s9ng3d45nklzxerg5096eaaj240708fa2n7uev5hrxvlrm8c9sa2t0kj')
        else:
            values = calc_pot(WALLET_API, wallet_id, FEE)

        # If Jackpot is below 1 ADA we must wait more cycles (less than 1 ADA transactiona are not allowed currently)
        if values[0] < 1000000:
            print('Jackpot after fees: ' +
                  str(values[0]) + '. Skipping this lottery')
            print('Wallet balance ' + str(values[2]))
            holdovers = lottery_entries
            continue
        else:
            holdovers.clear()

        last_winner = winner_address

        print('Collecting a fee of ' + str(values[1]))
        print('Paying out a jackpot of ' + str(values[0]))

        # Pay the fee to personal wallet
        payout(WALLET_API, wallet_id, PASSPHRASE, FEE_ADDRESS, values[1])

        # Payout Jackpot!
        payout(WALLET_API, wallet_id, PASSPHRASE, winner_address, values[0])


if __name__ == "__main__":
    start(init())
