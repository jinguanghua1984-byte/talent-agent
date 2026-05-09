"""adapters — 平台适配器注册表"""

from scripts.platform_match.adapters.maimai import MaimaiAdapter
from scripts.platform_match.adapters.boss import BossAdapter

ADAPTERS: dict[str, object] = {
    "maimai": MaimaiAdapter(),
    "boss": BossAdapter(),
}
