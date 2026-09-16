"""Systems that own external resources: assets, audio and save data."""

from managers.asset_manager import AssetManager, shared_asset_manager
from managers.audio_manager import AudioManager
from managers.resource_manager import ResourceManager
from managers.save_manager import SaveData, SaveManager

__all__ = [
    "AssetManager",
    "AudioManager",
    "ResourceManager",
    "SaveData",
    "SaveManager",
    "shared_asset_manager",
]
