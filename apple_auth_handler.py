# pip install pyjwt
# pip install jwt installs json web tokens.
import jwt
import requests
import time


IOS_BUNDLE_ID = "app.husn.husnios"
APPLE_PUBLIC_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_KEYS_EXPIRATION_PERIOD = 24 * 60 * 60 # automatically refresh every 24 hrs. 

apple_cached_keys = []
apple_keys_expiration = 0 

def fetch_apple_public_keys(force_refresh=False):
    global apple_cached_keys, apple_keys_expiration
    if force_refresh or time.time() > apple_keys_expiration:
        # Retry 5 times to retrieve the keys. 
        for _ in range(5):
            try:
                response = requests.get(APPLE_PUBLIC_KEYS_URL)
                response.raise_for_status()
                apple_cached_keys = response.json()["keys"]
                apple_keys_expiration = time.time() + APPLE_KEYS_EXPIRATION_PERIOD
                break
            except:
                print("CRITICAL: failed to retrieve apple public keys")
    return apple_cached_keys

def get_apple_key(kid):
    key = [k for k in fetch_apple_public_keys() if k['kid'] == kid]
    if key:
        key = key[0]
    else:
        # If key still doesn't exist someone probably tampered apple's sign in data. okay to raise error
        key = [k for k in fetch_apple_public_keys(force_refresh=True) if k['kid'] == kid][0]
    return jwt.algorithms.RSAAlgorithm.from_jwk(key)

def verify_apple_id_token(id_token):
    headers = jwt.get_unverified_header(id_token)
    public_key = get_apple_key(headers["kid"])

    decoded_token = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=IOS_BUNDLE_ID,
        issuer="https://appleid.apple.com",
    )
    return decoded_token
