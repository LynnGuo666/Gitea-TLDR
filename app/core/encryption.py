"""
敏感数据加密服务 - 基于 PyNaCl SealedBox（X25519 + XSalsa20-Poly1305）
"""

import base64
import binascii
import json
import logging
import threading
from pathlib import Path
from typing import Optional

from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, PublicKey, SealedBox

logger = logging.getLogger(__name__)


class EncryptionService:
    """对称加密服务，密钥存储于 work_dir/encryption.key"""

    KEY_FILE = "encryption.key"

    def __init__(self, key_path: Optional[str] = None):
        """
        初始化加密服务

        Args:
            key_path: 密钥文件路径，默认存储于 work_dir/encryption.key
        """
        self._key_path = key_path
        self._private_key: Optional[PrivateKey] = None
        self._public_key: Optional[PublicKey] = None
        self._lock = threading.Lock()

    @property
    def key_path(self) -> Path:
        """获取密钥文件路径"""
        if self._key_path:
            return Path(self._key_path)
        from app.core.config import settings

        return Path(settings.work_dir) / self.KEY_FILE

    def _ensure_key_exists(self) -> PrivateKey:
        """确保密钥文件存在，不存在则生成"""
        if self.key_path.exists():
            key_data = self.key_path.read_bytes()
            return PrivateKey(key_data)

        private_key = PrivateKey.generate()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.write_bytes(bytes(private_key))
        self.key_path.chmod(0o600)
        logger.info(f"生成新加密密钥: {self.key_path}")
        return private_key

    def _ensure_keys(self) -> PrivateKey:
        """确保密钥已加载（线程安全的双重检查锁定）"""
        if self._private_key is None:
            with self._lock:
                if self._private_key is None:
                    self._private_key = self._ensure_key_exists()
                    self._public_key = self._private_key.public_key
        return self._private_key

    def _get_encrypt_box(self) -> SealedBox:
        """获取用于加密的 Box（使用公钥）"""
        self._ensure_keys()
        return SealedBox(self._public_key)

    def _get_decrypt_box(self) -> SealedBox:
        """获取用于解密的 Box（使用私钥）"""
        self._ensure_keys()
        return SealedBox(self._private_key)

    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串，返回 base64 密文

        Args:
            plaintext: 待加密的明文字符串

        Returns:
            Base64 编码的密文字符串
        """
        if not plaintext:
            return plaintext
        ciphertext = self._get_encrypt_box().encrypt(plaintext.encode("utf-8"))
        return base64.b64encode(ciphertext).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """
        解密 base64 密文。

        - 若 base64 解码失败，认为是未加密的旧明文，静默返回原值（向后兼容）。
        - 若 base64 解码成功但解密失败（CryptoError），记录 ERROR 级别日志，
          说明可能存在密钥不匹配或数据损坏，返回原始密文。

        Args:
            ciphertext: Base64 编码的密文

        Returns:
            解密后的明文字符串；若为旧明文则返回原值；解密失败时返回原始密文并记录错误
        """
        if not ciphertext:
            return ciphertext
        # 尝试 base64 解码：失败则视为未加密的旧明文
        try:
            data = base64.b64decode(ciphertext.encode("ascii"))
        except (binascii.Error, ValueError):
            return ciphertext
        # base64 解码成功，尝试解密
        try:
            return self._get_decrypt_box().decrypt(data).decode("utf-8")
        except CryptoError:
            logger.error(
                "解密失败：数据为有效 base64 但无法用当前密钥解密，"
                "可能是密钥不匹配或数据损坏"
            )
            return ciphertext
        except (TypeError, UnicodeDecodeError) as exc:
            logger.error("解密后数据无法解码为 UTF-8: %s", exc)
            return ciphertext

    def encrypt_dict(self, data: dict) -> str:
        """
        加密字典（JSON 序列化后加密）

        Args:
            data: 待加密的字典

        Returns:
            Base64 编码的密文
        """
        return self.encrypt(json.dumps(data))

    def decrypt_dict(self, ciphertext: str) -> dict:
        """
        解密为字典

        Args:
            ciphertext: Base64 编码的密文

        Returns:
            解密后的字典
        """
        return json.loads(self.decrypt(ciphertext))


# 全局加密服务实例
encryption_service = EncryptionService()
