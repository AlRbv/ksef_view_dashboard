import os
import time
import requests
from dotenv import load_dotenv

import base64
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

load_dotenv()
BASE_URL = os.environ["KSEF_BASE_URL"]  
TIMEOUT = 10
NIP = os.environ["KSEF_NIP"]
KSEF_TOKEN = os.environ["KSEF_TOKEN"]

def authenticate(base_url: str, nip: str, ksef_token: str, timeout: int = 10) -> dict:

    # PUBLIC KEY FETCHING
    resp = requests.get(f"{base_url}/security/public-key-certificates", timeout=timeout)
    resp.raise_for_status()
    certs = resp.json()

    def  get_token_cert(certs: list[dict]) -> str: 
        for cert in certs:
            if "KsefTokenEncryption" in cert["usage"]:
                return cert["certificate"]
        raise RuntimeError("No KsefTokenEncryption certificate found")

    cert_b64 = get_token_cert(certs)

    # GETTING CHALLENGE 
    resp = requests.post(f"{base_url}/auth/challenge", timeout=timeout)
    resp.raise_for_status()
    challenge = resp.json()

    challenge_code = challenge["challenge"]
    timestamp_ms = challenge["timestampMs"]

    # combining "letter" to auth in KSeF
    letter = f"{ksef_token}|{timestamp_ms}"

    # authenticating via public key and challenge encryption
    cert_bytes = base64.b64decode(cert_b64)
    public_key = x509.load_der_x509_certificate(cert_bytes).public_key()

    sealed = public_key.encrypt(
        letter.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    encrypted_token = base64.b64encode(sealed).decode()

    body = {
        "challenge": challenge_code,
        "contextIdentifier": {"type": "Nip", "value": nip} ,
        "encryptedToken": encrypted_token,
    }

    resp = requests.post(f"{base_url}/auth/ksef-token", json=body, timeout=timeout)
    resp.raise_for_status()
    auth = resp.json()

    auth_token = auth["authenticationToken"]["token"]
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }

    # WAITING FOR KSEF TO VERIFY THE TOKEN
    ref = auth["referenceNumber"]
    for attempt in range(30):
        resp = requests.get(f"{base_url}/auth/{ref}", headers=headers, timeout=timeout)
        resp.raise_for_status()
        status = resp.json()["status"]
        if status["code"] == 200:
            break
        if status["code"] >= 400:
            raise RuntimeError(f"Auth failed: {status}")
        time.sleep(1)
    else:
        raise RuntimeError("Auth still pending after 30 s")

    # getting the access and refresh tokens for longer access to the system

    resp = requests.post(f"{base_url}/auth/token/redeem", headers=headers, timeout=timeout)
    resp.raise_for_status()
    tokens = resp.json()
    print("Access token valid until:", tokens["accessToken"]["validUntil"])

    return tokens

if __name__ == "__main__":
    tokens = authenticate(BASE_URL, NIP, KSEF_TOKEN)
    print("Auth OK, valid until:", tokens["accessToken"]["validUntil"])
