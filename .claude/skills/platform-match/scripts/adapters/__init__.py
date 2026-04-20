"""adapters — 平台适配器注册表"""

from adapters.maimai import MaimaiAdapter

ADAPTERS: dict[str, object] = {
    "maimai": MaimaiAdapter(),
}
