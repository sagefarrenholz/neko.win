#!./bin/python
from typing import final
import requests
import os
import time

from src.new_wallet import new_wallet
from src.util import *

WALLET_API = os.environ.get('WALLET_API') or 'http://127.0.0.1:8090/v2/'
# interval to payout the pot in seconds
SWEEP_INTERVAL = int(os.environ.get('SWEEP_INTERVAL') or (10))

PASSPHRASE = os.environ.get('PASSPHRASE')  # transaction passphrase

FEE_ADDRESS = os.environ.get('FEE_ADDRESS')  # where to send collected fees
FEE = 0.05  # amount of fee that is taken from the jackpot payout

def record(filename, to_write):
    fd = os.open('logs/' + filename, os.O_WRONLY | os.O_TRUNC | os.O_CREAT)
    os.write(fd, str.encode(str(to_write)))
    os.close(fd)


def init():
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
    last_sweep = now()
    print('\nStarting Neko.Win')

    while True:
        print('\nNew lottery! Starting time ' + str(last_sweep))
        print('Waiting ' + str(SWEEP_INTERVAL) + 's for entrants')

        # Sleep for Sweep interval
        time.sleep(SWEEP_INTERVAL)

        # Save the sweep time for record keeping
        last_last_sweep = last_sweep

        # Get all entries since last_sweep
        lottery_entries = entries(WALLET_API, wallet_id, last_sweep)

        # Set last_sweep to now
        last_sweep = now()

        # Log the entrants incase of refunding, etc
        record("entries_from_" + str(last_last_sweep), lottery_entries)

        # If there are no entries, do not draw a winner
        if len(lottery_entries) <= 0:
            print('No one entered the lottery :(')
            continue

        # Randomly choose winner and payout to their address
        winner_address = draw_winner(lottery_entries)
        print(str(winner_address) + ' was drawn as the winner!')
        pot_amount = calc_pot(WALLET_API, wallet_id, FEE)
        print('Paying out a jackpot of ' + str(pot_amount))
        payout(WALLET_API, wallet_id, PASSPHRASE, winner_address, pot_amount)

        # Pay the fee to personal wallet
        #payout(WALLET_API, wallet_id, PASSPHRASE, FEE_ADDRESS, FEE)

if __name__ == "__main__":
    start(init())
