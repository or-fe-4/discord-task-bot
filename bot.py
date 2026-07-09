"""
Discord Bot本体。

できること:
  1. 指定チャンネルで毎日 NOTIFY_HOUR:NOTIFY_MINUTE (JST) にタスク一覧を通知
  2. 指定チャンネルでの発言に、設定した口調(PERSONA_PROMPT)でGeminiが返信
  3. /task add / /task remove / /task list でタスクを管理

起動方法: python bot.py (.envに必要な値を入れておくこと)
"""
import logging
from datetime import time as dtime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks

import config
import gemini_client
import tasks_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("task-bot")

JST = ZoneInfo("Asia/Tokyo")

intents = discord.Intents.default()
intents.message_content = True  # チャット機能に必須


class TaskBotClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        # チャンネルごとの直近の会話履歴。Bot再起動でリセットされるが、
        # 雑談用途なのでDBに永続化するほどのものではないと判断。
        self.chat_history: dict[int, list[dict]] = {}

    async def setup_hook(self):
        # スラッシュコマンドをDiscordに登録する
        await self.tree.sync()
        daily_task_notification.start()


client = TaskBotClient()


# ---------------------------------------------------------------------------
# タスク管理コマンド (/task add, /task remove, /task list)
# ---------------------------------------------------------------------------
task_group = app_commands.Group(name="task", description="タスクの管理")


@task_group.command(name="add", description="タスクを追加する")
@app_commands.describe(description="タスクの内容")
async def task_add(interaction: discord.Interaction, description: str):
    task = tasks_db.add_task(description)
    await interaction.response.send_message(
        f"タスクを追加したよ: `#{task.id}` {task.description}"
    )


@task_group.command(name="remove", description="タスクを削除する")
@app_commands.describe(task_id="削除するタスクのID (一覧に表示される番号)")
async def task_remove(interaction: discord.Interaction, task_id: int):
    if tasks_db.remove_task(task_id):
        await interaction.response.send_message(f"タスク `#{task_id}` を削除したよ")
    else:
        await interaction.response.send_message(
            f"`#{task_id}` というタスクは見つからなかった", ephemeral=True
        )


@task_group.command(name="edit", description="タスクの内容を編集する")
@app_commands.describe(
    task_id="編集するタスクのID (一覧に表示される番号)",
    new_description="新しいタスクの内容",
)
async def task_edit(interaction: discord.Interaction, task_id: int, new_description: str):
    if tasks_db.update_task(task_id, new_description):
        await interaction.response.send_message(
            f"タスク `#{task_id}` を更新したよ: {new_description}"
        )
    else:
        await interaction.response.send_message(
            f"`#{task_id}` というタスクは見つからなかった", ephemeral=True
        )


@task_group.command(name="list", description="現在のタスク一覧を表示する")
async def task_list(interaction: discord.Interaction):
    await interaction.response.send_message(format_task_list())


client.tree.add_command(task_group)


def format_task_list() -> str:
    task_items = tasks_db.list_tasks()
    if not task_items:
        return "今のところタスクはないよ📭"
    lines = [f"- `#{t.id}` {t.description}" for t in task_items]
    return "**現在のタスク一覧**\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# 毎朝6:00のタスク通知
# ---------------------------------------------------------------------------
@tasks.loop(time=dtime(hour=config.NOTIFY_HOUR, minute=config.NOTIFY_MINUTE, tzinfo=JST))
async def daily_task_notification():
    channel = client.get_channel(config.CHANNEL_ID)
    if channel is None:
        logger.warning("CHANNEL_ID のチャンネルが見つかりません")
        return

    task_list_text = format_task_list()

    # 一言コメントもGeminiに作ってもらう(失敗しても通知自体は送る)
    comment = ""
    try:
        comment = gemini_client.generate_reply(
            system_prompt=config.PERSONA_PROMPT,
            history=[],
            user_message=(
                "おはようの挨拶と一緒に、今日も一日頑張ろうと思えるような"
                "短い一言(1文だけ)をください。タスクの内容には触れなくていいです。"
            ),
        )
    except Exception:
        logger.exception("朝の一言コメント生成に失敗しました")

    message = f"おはよう☀️\n\n{task_list_text}"
    if comment:
        message += f"\n\n{comment}"

    await channel.send(message)


@daily_task_notification.before_loop
async def before_daily_task_notification():
    await client.wait_until_ready()


# ---------------------------------------------------------------------------
# 雑談(指定チャンネルでの通常発言に反応)
# ---------------------------------------------------------------------------
@client.event
async def on_ready():
    logger.info("ログイン完了: %s", client.user)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id != config.CHANNEL_ID:
        return
    if message.content.startswith("/"):
        return

    history = client.chat_history.setdefault(message.channel.id, [])

    async with message.channel.typing():
        try:
            reply = gemini_client.generate_reply(
                system_prompt=config.PERSONA_PROMPT,
                history=history,
                user_message=message.content,
            )
        except Exception:
            logger.exception("Gemini応答の生成に失敗しました")
            await message.reply("うーん、ちょっと今うまく返事できないみたい…")
            return

    history.append({"role": "user", "text": message.content})
    history.append({"role": "model", "text": reply})
    # 履歴が伸びすぎないように直近N往復だけ残す
    max_len = config.CHAT_HISTORY_TURNS * 2
    if len(history) > max_len:
        del history[: len(history) - max_len]

    await message.reply(reply)


def main():
    tasks_db.init_db()
    client.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
