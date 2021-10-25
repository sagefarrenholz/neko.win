import random
import requests
import datetime

seeded = False


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def create_address(wallet_api: str) -> str:
    """ Return lottery entries since 'since' iso timestamp returns the next timestamp """
    res = requests.post(wallet_api + 'addresses')
    if res.status_code != 200:
        print(res.json()['message'])
        raise RuntimeError('Something went wrong creating address. Status: ' +
                           str(res.status_code))

    return res.json()['inputs']


def entries(wallet_api: str, wallet_id: str, since: str, explorer_api: str = 'https://explorer-api.mainet.dandelion.link/api') -> dict:
    """ Return lottery entries since 'since' iso timestamp returns the next timestamp """
    res = requests.get(wallet_api + 'wallets/' + str(wallet_id) + '/transactions', params={
        'start': since
    })
    if res.status_code != 200:
        print(res.json()['message'])
        raise RuntimeError(
            'Could not collect entries. HTTP status: ' +
            str(res.status_code))

    entries = dict()
    for transaction in res.json():
        if transaction['direction'] == 'outgoing':
            continue

        if "address" in transaction['inputs'][0]:
            address = transaction['inputs'][0]['address']
        else:
            res = requests.get(
                explorer_api + 'txs/summary/' + transaction['id'])
            if res.status_code != 200:
                print(res.json()['message'])
                raise RuntimeError(
                    'Failed to fetch transaction data from explorer api. HTTP status: ' +
                    str(res.status_code))
            address = res.json()['Right']['ctsInputs'][0]['ctaAddress']

        if address in entries:
            entries[address] += int(transaction['amount']['quantity'])
        else:
            entries[address] = int(transaction['amount']['quantity'])

    return entries


def payout(wallet_api: str, wallet_id: str, passphrase: str, winner_wallet: str, amount: int):
    """ Pay specified amount to winner_wallet address """
    res = requests.post(wallet_api + 'wallets/' + str(wallet_id) + '/transactions', json={
        'passphrase': passphrase,
        'payments': [
            {
                'address': winner_wallet,
                'amount': amount
            }
        ]
    })
    if res.status_code != 202:
        print(res.json()['message'])
        raise RuntimeError(
            'Could not send payout transaction. HTTP status: ' +
            str(res.status_code))

    return res.json()


def wallet_balance(wallet_api: str, wallet_id: str) -> int:
    """ Return the available amount of cardano in the wallet """
    res = requests.get(wallet_api + 'wallets/' + str(wallet_id))
    if res.status_code != 200:
        print(res.json()['message'])
        raise RuntimeError(
            'Could not retrieve wallet balance. HTTP status: ' +
            str(res.status_code))

    return int(res.json()['balance']['available']['quantity'])


def calc_pot(wallet_api: str, wallet_id: str, fee: float, dummy_id: str = 'addr1qy35zl8g9qf34akgeya8frrcd0kv2gud8r59huypsjq39wzyjp6e6as72as4rnsxlytshdsy5jq6x4yhzgq4x6rnq5ts3ktffg') -> int:
    """ Calculate the actual winnable pot amount (minus pot fee and transaction fees) in LOVELACE"""
    wallet_bal = wallet_balance(wallet_api, wallet_id)

    # Estimate payout transacation fee
    res = requests.post(wallet_api + 'wallets/' + str(wallet_id) + '/payment-fees', json={
        'payments': [
            {
                'address': dummy_id,
                'amount': str(int(wallet_bal * (1.0 - fee)))
            }
        ]
    })
    if res.status_code != 202:
        print(
            'Something went wrong estimating trans fees. Status: ' +
            str(res.status_code))
        print(res.json()['message'])
        exit(-1)

    # Estimate pot_fee transacation fee
    res2 = requests.post(wallet_api + 'wallets/' + str(wallet_id) + '/payment-fees', json={
        'payments': [
            {
                'address': dummy_id,
                'amount': str(int(wallet_bal * fee))
            }
        ]
    })
    if res2.status_code != 202:
        print(
            'Something went wrong estimating pot trans fees. Status: ' +
            str(res.status_code))
        print(res.json()['message'])
        exit(-1)

    payout_trans_fee = int(res.json()['estimated_max']['quantity'])
    pot_trans_fee = int(res2.json()['estimated_max']['quantity'])
    return int(wallet_bal * (1.0 - fee)) - (payout_trans_fee + pot_trans_fee)


def draw_winner(addresses_with_amounts: dict) -> str:
    """ Returns a randomly selected winner (address) """
    global seeded
    if not seeded:
        random.seed()
        seeded = True
    entrants = list(addresses_with_amounts.keys())
    amounts = list(addresses_with_amounts.values())
    # Randomly choose based on weight sampling
    return random.choices(entrants, weights=amounts, k=1)[0]
