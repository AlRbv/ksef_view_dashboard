import os
import time
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv

import base64
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

load_dotenv()
TIMEOUT = 10

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

# Add check for expired token to keep the session until token is about to expire

class KsefClient:
    def __init__(self, base_url: str, nip: str, ksef_token: str):
        self.base_url = base_url
        self.nip = nip
        self.ksef_token = ksef_token
        self._tokens = None

    def _access(self) -> str:
        if self._tokens is not None:                                  
            valid_until = datetime.fromisoformat(
                self._tokens["accessToken"]["validUntil"].replace("Z", "+00:00")
            )
            if valid_until - datetime.now(timezone.utc) > timedelta(seconds=60):
                return self._tokens["accessToken"]["token"]

        self._tokens = authenticate(self.base_url, self.nip, self.ksef_token)
        return self._tokens["accessToken"]["token"]

    def query_metadata_page(self, subject_type: str, date_from: str, date_to: str, 
                            page_offset: int = 0, page_size: int = 10) -> dict:
        body = {
            "subjectType": subject_type,
            "dateRange": {"dateType": "Issue", "from": date_from, "to": date_to},
        }

        resp = requests.post(
            f"{self.base_url}/invoices/query/metadata",                
            params={"pageOffset": page_offset, "pageSize": page_size},
            headers={"Authorization": f"Bearer {self._access()}"},    
            json=body,
            timeout=TIMEOUT,
        )
        print(resp.status_code)
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    load_dotenv()
    client = KsefClient(
        os.environ["KSEF_BASE_URL"],
        os.environ["KSEF_NIP"],
        os.environ["KSEF_TOKEN"],
    )
    page = client.query_metadata_page("Subject1", "2026-10-01T00:00:00Z", "2026-10-27T23:59:59Z")
    print(page.keys())
    if page["invoices"]:
        print(page["invoices"][0])