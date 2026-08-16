"""
Orchestrator: the "brain" that takes a natural-language request, decides
which skill(s) to call using tool-calling, executes them, and returns a
final spoken/text reply.
"""

import datetime
import json

from groq_client import chat_completion
from skills import registry
import config

MODEL = config.MODEL
TODAY = datetime.date.today().isoformat()

SYSTEM_PROMPT = f"""You are Jarvis, a personal automation assistant running on the \
user's own computer. Today's date is {TODAY}.

Your own knowledge has a training cutoff and may be outdated. For anything \
involving current events, recent posts, latest news, weather, or "what's \
happening now", you MUST use the appropriate tool (web_search, news_briefing, \
get_weather) rather than answering from memory. Never guess, invent, or \
fabricate a URL, quote, number, or specific fact — only state things a tool \
result actually returned to you. If a search doesn't return what's needed, \
say so honestly instead of making something up.

Only use open_app when the user explicitly asks you to open something (an \
app, file, or a URL they gave you). Never open a browser as a side effect of \
answering an informational question like weather or news — use the correct \
data tool instead, and just tell the user the answer in words.

You have access to tools that let you check tasks, open apps, search the web, \
tell the time/weather, etc. Use tools whenever a request maps to one of them. \
Keep replies short and conversational — this may be read aloud by a \
text-to-speech engine, so avoid markdown, bullet points, or long lists unless \
the user asked to see something written out."""


class Orchestrator:
    def __init__(self, model: str = MODEL):
        self.model = model
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def handle(self, user_text: str) -> str:
        self.history.append({"role": "user", "content": user_text})

        # Cap the loop so a confused model can't spin forever
        for _ in range(8):
            response = chat_completion(
                model=self.model,
                messages=self.history,
                tools=registry.openai_tool_schemas(),
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                self.history.append({"role": "assistant", "content": message.content or ""})
                return (message.content or "").strip()

            self.history.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )

            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = registry.run(tc.function.name, **args)
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        return "Sorry, I got stuck reasoning about that — try rephrasing."

    def reset(self) -> None:
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]


if __name__ == "__main__":
    orch = Orchestrator()
    print(f"Jarvis orchestrator ready (model={orch.model}). Type a request (Ctrl+C to quit).")
    while True:
        try:
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            break
        if not user_input.strip():
            continue
        reply = orch.handle(user_input)
        print(f"Jarvis: {reply}")
