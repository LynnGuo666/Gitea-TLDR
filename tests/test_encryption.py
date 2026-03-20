"""
加密服务测试
"""

import pytest
import tempfile
from pathlib import Path

from app.core.encryption import EncryptionService


class TestEncryptionService:
    """加密服务测试"""

    def setup_method(self):
        """每个测试方法前创建临时密钥目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.key_path = str(Path(self.temp_dir) / "test_key")
        self.service = EncryptionService(key_path=self.key_path)

    def teardown_method(self):
        """清理临时文件"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_encrypt_decrypt_roundtrip(self):
        """测试加密解密往返"""
        original = "sk-ant-api03-xxx-yyy-zzz"
        encrypted = self.service.encrypt(original)

        assert encrypted != original
        assert encrypted != ""
        assert self.service.decrypt(encrypted) == original

    def test_encrypt_produces_different_ciphertext(self):
        """相同明文应产生不同密文（SealedBox 使用随机 nonce）"""
        original = "same-secret-token"
        encrypted1 = self.service.encrypt(original)
        encrypted2 = self.service.encrypt(original)

        assert encrypted1 != encrypted2
        assert self.service.decrypt(encrypted1) == original
        assert self.service.decrypt(encrypted2) == original

    def test_encrypt_empty_string(self):
        """空字符串应直接返回"""
        assert self.service.encrypt("") == ""
        assert self.service.decrypt("") == ""

    def test_encrypt_none_handled(self):
        """None 输入应直接返回"""
        assert self.service.encrypt(None) is None  # type: ignore
        assert self.service.decrypt(None) is None  # type: ignore

    def test_backwards_compat_unencrypted_data(self):
        """旧版本未加密的明文数据应能正常解密（回退为明文）"""
        plain_token = "old_plain_text_token"
        decrypted = self.service.decrypt(plain_token)

        assert decrypted == plain_token

    def test_encrypt_dict_roundtrip(self):
        """测试字典加密解密往返"""
        original = {
            "access_token": "token123",
            "refresh_token": "refresh456",
            "scope": "read:user read:repository",
        }
        encrypted = self.service.encrypt_dict(original)
        decrypted = self.service.decrypt_dict(encrypted)

        assert decrypted == original
        assert decrypted["access_token"] == "token123"

    def test_key_persistence(self):
        """相同密钥路径应复用同一密钥"""
        service1 = EncryptionService(key_path=self.key_path)
        service2 = EncryptionService(key_path=self.key_path)

        secret = "test-secret"
        encrypted = service1.encrypt(secret)
        decrypted = service2.decrypt(encrypted)

        assert decrypted == secret

    def test_different_key_cannot_decrypt(self):
        """不同密钥应无法解密对方加密的数据"""
        service1 = EncryptionService(key_path=self.key_path)

        other_key_path = str(Path(self.temp_dir) / "other_key")
        service2 = EncryptionService(key_path=other_key_path)

        secret = "super-secret"
        encrypted = service1.encrypt(secret)

        # service2 使用不同密钥，解密会失败（返回原值或报错）
        decrypted = service2.decrypt(encrypted)
        assert decrypted != secret

    def test_key_file_permissions(self):
        """密钥文件权限应为 0o600（仅所有者可读写）"""
        import os

        _ = self.service.encrypt("test")
        key_file = Path(self.key_path)

        assert key_file.exists()
        mode = os.stat(key_file).st_mode & 0o777
        assert mode == 0o600

    def test_very_long_secret(self):
        """超长密钥也应能正常加解密"""
        long_secret = "x" * 10000
        encrypted = self.service.encrypt(long_secret)
        decrypted = self.service.decrypt(encrypted)

        assert decrypted == long_secret

    def test_unicode_secret(self):
        """Unicode 字符应能正常加解密"""
        unicode_secret = "密钥🔐-token-токен"
        encrypted = self.service.encrypt(unicode_secret)
        decrypted = self.service.decrypt(encrypted)

        assert decrypted == unicode_secret
