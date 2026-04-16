"""NoneBot2 entry point for Meme Downloader QQ Bot."""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# Load the meme plugin
nonebot.load_plugin("meme_downloader.bot.plugin")

if __name__ == "__main__":
    nonebot.run()
