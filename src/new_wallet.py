from mnemonic import Mnemonic
import requests
import os
import time


def new_wallet(wallet_api, passphrase, verbose=False):
    if verbose:
        print('Generating a new wallet')
    mnemo = Mnemonic('english')
    words = mnemo.generate(strength=256)
    words_split = words.split()
    res = requests.post(wallet_api + 'wallets', json={
        'name': 'pot',
        'mnemonic_sentence': words_split,
        'passphrase': passphrase,
    })
    if res.status_code != 201:
        print(res.json()['message'])
        raise RuntimeError(
            'Could not generate a new wallet. HTTP status: ' +
            str(res.status_code))

    if verbose:
        print('Successfully created wallet')
    with os.open('.mnemonic', os.O_WRONLY | os.O_TRUNC | os.O_CREAT) as fd:
         os.write(fd, str.encode(words))
    print(
        '\033[1m' +
        """A BIP-0039 mnemonic recovery phrase has been generated for your new wallet in `.mnemonic`
Copy this phrase onto a piece of paper and then delete (or better yet shred) the file.
Restart neko.win after securing your mnemonic, the newest wallet will be automatically used.\n""" +
        '\033[0m')
    time.sleep(2)

    return res.json()['id']


def delete_walet(walet_api, id):
    pass
