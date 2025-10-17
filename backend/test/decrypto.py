#decrypto.py
import os
import json
import base64
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from typing import Dict

def decrypt_file(file_path: str, private_key_path: str = None) -> Dict:
    """
    读取加密文件并解密，返回解密后的 dict。
    参数:
      - file_path: 加密文件的完整路径
      - private_key_path: 私钥文件路径，若为 None 则使用当前工作目录下的 private.pem
    抛出:
      - FileNotFoundError: 文件或私钥不存在
      - ValueError: 解密/校验失败（如 tag 校验失败）
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"加密文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        enc_data = json.load(f)

    try:
        enc_key = base64.b64decode(enc_data["key"])
        nonce = base64.b64decode(enc_data["nonce"])
        tag = base64.b64decode(enc_data["tag"])
        ciphertext = base64.b64decode(enc_data["data"])
    except KeyError as e:
        raise ValueError(f"加密文件格式不正确，缺少字段: {e}")

    pk_path = private_key_path or os.path.join(os.getcwd(), "private.pem")
    if not os.path.exists(pk_path):
        raise FileNotFoundError(f"私钥文件不存在: {pk_path}")

    with open(pk_path, "rb") as f:
        private_key = RSA.import_key(f.read())

    # RSA 解密 AES key
    cipher_rsa = PKCS1_OAEP.new(private_key)
    try:
        aes_key = cipher_rsa.decrypt(enc_key)
    except ValueError as e:
        raise ValueError(f"RSA 解密失败（可能私钥不匹配或密文被篡改）: {e}")

    # AES-GCM 解密并 verify
    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher_aes.decrypt_and_verify(ciphertext, tag)
    except ValueError as e:
        raise ValueError(f"AES-GCM 解密/验证失败（tag mismatch，可能数据被篡改或密钥错误）: {e}")

    try:
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"解密后数据解析为 JSON 失败: {e}")

result = decrypt_file(r".json", private_key_path=r".pem")
print(result)
