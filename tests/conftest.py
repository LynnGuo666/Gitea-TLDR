from __future__ import annotations

import asyncio
import inspect
import os
import sys
import types


if "nacl" not in sys.modules:
    nacl_module = types.ModuleType("nacl")
    nacl_exceptions = types.ModuleType("nacl.exceptions")
    nacl_public = types.ModuleType("nacl.public")

    class CryptoError(Exception):
        pass

    class PublicKey:
        def __init__(self, data: bytes | None = None):
            self._data = data or b"test-public-key"

        def __bytes__(self):
            return self._data

    class PrivateKey:
        def __init__(self, data: bytes | None = None):
            self._data = data or b"test-private-key"
            self.public_key = PublicKey(self._data)

        @staticmethod
        def generate():
            return PrivateKey(os.urandom(32))

        def __bytes__(self):
            return self._data

    class SealedBox:
        def __init__(self, key):
            self.key = key

        def encrypt(self, payload: bytes) -> bytes:
            key_bytes = bytes(self.key) if hasattr(self.key, "__bytes__") else b"key"
            nonce = os.urandom(8).hex().encode("ascii")
            return key_bytes.hex().encode("ascii") + b":" + nonce + b":" + payload

        def decrypt(self, payload: bytes) -> bytes:
            key_bytes = bytes(self.key) if hasattr(self.key, "__bytes__") else b"key"
            expected = key_bytes.hex().encode("ascii") + b":"
            if not payload.startswith(expected):
                raise CryptoError("wrong key")
            parts = payload.split(b":", 2)
            if len(parts) != 3:
                raise CryptoError("invalid payload")
            return parts[2]

    nacl_exceptions.CryptoError = CryptoError
    nacl_public.PrivateKey = PrivateKey
    nacl_public.PublicKey = PublicKey
    nacl_public.SealedBox = SealedBox

    nacl_module.exceptions = nacl_exceptions
    nacl_module.public = nacl_public

    sys.modules["nacl"] = nacl_module
    sys.modules["nacl.exceptions"] = nacl_exceptions
    sys.modules["nacl.public"] = nacl_public


def pytest_pyfunc_call(pyfuncitem):
    """为仓库内少量 asyncio 测试提供最小运行适配。

    这样在未安装 pytest-asyncio 的环境里，带协程函数的测试也能执行。
    """
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    func_args = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
    }
    asyncio.run(test_func(**func_args))
    return True
