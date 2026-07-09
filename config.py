"""
Gemini APIをREST経由で直接叩くモジュール。
公式SDK(google-genai)は破壊的変更が多いので、あえてrequestsで薄く叩く形にして
挙動を追いやすくしている。エンドポイントの形が変わらない限りメンテは楽なはず。
"""
import time

import requests

import config

_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

# 503(混雑)や429(レート制限)は一時的なことが多いので、短い間隔で数回だけ再試行する
_RETRYABLE_STATUS = {429, 503}
_MAX_RETRIES = 2
_RETRY_DELAY_SECONDS = 2


def generate_reply(system_prompt: str, history: list[dict], user_message: str) -> str:
    """
    system_prompt: キャラクター設定(口調など)
    history: [{"role": "user"|"model", "text": "..."}] の過去のやり取り
    user_message: 今回のユーザー発言
    """
    contents = []
    for turn in history:
        contents.append(
            {"role": turn["role"], "parts": [{"text": turn["text"]}]}
        )
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 300,
            "temperature": 0.9,
        },
    }

    url = _ENDPOINT.format(model=config.GEMINI_MODEL)

    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        resp = requests.post(
            url,
            params={"key": config.GEMINI_API_KEY},
            json=payload,
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            try:
                candidate = data["candidates"][0]
                parts = candidate["content"]["parts"]
                return "".join(p.get("text", "") for p in parts).strip()
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Gemini APIの応答形式が想定外です: {data}") from e

        last_error = RuntimeError(
            f"Gemini API error {resp.status_code}: {resp.text}"
        )

        if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
            time.sleep(_RETRY_DELAY_SECONDS * (attempt + 1))
            continue

        # リトライ対象外のエラー、またはリトライ回数を使い切った
        raise last_error

    raise last_error