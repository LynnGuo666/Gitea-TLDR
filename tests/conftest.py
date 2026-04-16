from __future__ import annotations

import asyncio
import inspect


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
