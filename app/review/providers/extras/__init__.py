"""legacy CLI providers（claude_code、codex_cli）。

只有在 `settings.enable_legacy_providers=True` 时才会被 ProviderRegistry 导入。
默认情况下，应用根本不会执行此包的初始化代码——任何依赖 CLI 可执行文件的
导入副作用都不会在 Forge-only 模式下产生影响。
"""
