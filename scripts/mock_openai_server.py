from __future__ import annotations

import asyncio
import json

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    if not payload.get("stream"):
        return {
            "choices": [
                {
                    "message": {
                        "content": "付款条件是验收后30日内付款。[1]"
                    }
                }
            ],
            "usage": {"total_tokens": 16},
        }

    async def events():
        for token in ["付款条件是", "验收后", "30日内付款。", "[1]"]:
            yield (
                "data: "
                + json.dumps(
                    {"choices": [{"delta": {"content": token}}]},
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            await asyncio.sleep(0.03)
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="warning")
