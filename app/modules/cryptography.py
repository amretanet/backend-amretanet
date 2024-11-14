from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64
import os
from dotenv import load_dotenv

load_dotenv()


async def RSADecryption(ciphertext):
    rsa_private_key_pem = f"-----BEGIN RSA PRIVATE KEY-----\n{os.environ['RSA_PRIVATE_KEY'].strip()}\n-----END RSA PRIVATE KEY-----"
    rsa_private_key = serialization.load_pem_private_key(
        rsa_private_key_pem.encode("utf-8"),
        password=None,
    )
    ciphertext_bytes = base64.b64decode(ciphertext)
    plaintext = rsa_private_key.decrypt(ciphertext_bytes, padding.PKCS1v15())

    return plaintext.decode("utf-8")


async def RSAEncryption(plaintext):
    rsa_public_key_pem = f"-----BEGIN PUBLIC KEY-----\n{os.environ['RSA_PUBLIC_KEY'].strip()}\n-----END PUBLIC KEY-----"
    rsa_public_key = serialization.load_pem_public_key(
        rsa_public_key_pem.encode("utf-8")
    )
    ciphertext = rsa_public_key.encrypt(
        plaintext.encode("utf-8"),
        padding.PKCS1v15(),
    )
    ciphertext_base64 = base64.b64encode(ciphertext).decode("utf-8")

    return ciphertext_base64
