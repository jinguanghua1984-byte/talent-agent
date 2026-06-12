"""人才库云同步共享常量和错误类型。"""

from __future__ import annotations


STATE_SCHEMA = "talent_cloud_state_v2"
LEGACY_STATE_SCHEMA = "talent_cloud_state_v1"
INDEX_SCHEMA = "talent_cloud_bundle_index_v1"
REMOTE_SCHEMA = "talent_cloud_remote_v1"


class CloudSyncError(RuntimeError):
    """可恢复的云同步错误。"""
