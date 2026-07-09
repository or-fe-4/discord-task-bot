"""
.envから設定を読み込んで、他のモジュールから使えるようにするだけのファイル。
値は起動時に一度だけ読まれる。
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"環境変数 {name} が設定されていません。.env を確認してください。"
        )
    return value


DISCORD_TOKEN = _require("DISCORD_TOKEN")
GEMINI_API_KEY = _require("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
CHANNEL_ID = int(_require("CHANNEL_ID"))
NOTIFY_HOUR = int(os.getenv("NOTIFY_HOUR", "6"))
NOTIFY_MINUTE = int(os.getenv("NOTIFY_MINUTE", "0"))
PERSONA_PROMPT = os.getenv(
    "PERSONA_PROMPT",
    "あなたはフレンドリーなアシスタントです。タメ口で簡潔に話してください。",
)

# チャット履歴として何往復分を覚えておくか(長くしすぎるとトークン代がかさむので注意)
CHAT_HISTORY_TURNS = 6

DB_PATH = os.getenv("DB_PATH", "tasks.db")
