"""adapters — 平台适配器注册表"""

from adapters.maimai import MaimaiAdapter
from adapters.boss import BossAdapter

ADAPTERS: dict[str, object] = {
    "maimai": MaimaiAdapter(),
    "boss": BossAdapter(),
}
