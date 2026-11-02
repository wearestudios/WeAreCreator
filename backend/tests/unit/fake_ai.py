"""A provider that never touches the network, for every AI test.

`replies` is consumed in order; each is a string (the model's text), a
callable `(system, user) -> str`, or an exception instance to raise. Every
call is recorded with exactly what would have been sent, which is what the
leak tests search.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import ai


class FakeProvider:
    name = "fake"

    def __init__(self, *replies, input_tokens=1200, output_tokens=240):
        self.replies = list(replies)
        self.calls: list = []
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    async def complete(self, *, model, system, user, json_schema, max_output_tokens, timeout_s):
        self.calls.append(
            {"model": model, "system": system, "user": user, "schema": json_schema,
             "max_output_tokens": max_output_tokens, "timeout_s": timeout_s}
        )
        if not self.replies:
            raise AssertionError("the fake provider was called more often than scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        text = reply(system, user) if callable(reply) else reply
        return ai.ProviderResult(
            text=text, input_tokens=self.input_tokens, output_tokens=self.output_tokens
        )

    def sent(self) -> str:
        """Everything that left the server, joined — what a leak test searches."""
        return "\n".join(c["system"] + "\n" + c["user"] for c in self.calls)


@contextmanager
def ai_on(provider, **env):
    """AI switched on with `provider` installed, and everything put back."""
    keys = {"AI_ENABLED": "true", **env}
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update(keys)
    ai.use_provider(provider)
    try:
        yield provider
    finally:
        ai.use_provider(None)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
