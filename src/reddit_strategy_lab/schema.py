from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Post(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    url: str
    subreddit: str
    title: str = Field(max_length=1000)
    body: str = Field(max_length=30000)
    published_at: str
    collected_at: str
    edited_at: str | None = None
    access_method: Literal["manual", "local_import", "reddit_oauth", "public_web"]

    content_scope: Literal["post_body", "excerpt"] = "post_body"
    publication_precision: Literal["timestamp", "date", "unknown"] = "timestamp"

    @model_validator(mode="after")
    def dates(self):
        dates = [self.collected_at, self.edited_at]
        if self.publication_precision == "timestamp":
            dates.append(self.published_at)
        elif self.publication_precision == "date":
            from datetime import date

            date.fromisoformat(self.published_at)
        for value in dates:
            if value is not None and datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
                raise ValueError("source timestamps require timezone")
        if not re.fullmatch(
            r"https://(?:www\.)?reddit\.com/r/[A-Za-z0-9_]+/comments/[a-z0-9]+(?:/[^?#]*)?", self.url
        ):
            raise ValueError("canonical Reddit post URL required")
        return self

    @property
    def content_hash(self):
        return hashlib.sha256((self.title + "\n" + self.body).encode()).hexdigest()


class Expr(Strict):
    op: Literal[
        "const", "field", "lag", "sma", "std", "min", "max", "add", "sub", "mul", "div", "abs", "return"
    ]
    value: float | None = None
    field: (
        Literal[
            "open",
            "high",
            "low",
            "close",
            "volume",
            "minutes_to_close",
            "bars_held",
            "sessions_held",
            "entry_price",
        ]
        | None
    ) = None
    window: int | None = Field(default=None, ge=1, le=500)
    args: list[Expr] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def shape(self):
        arity = 0 if self.op in ("const", "field") else 2 if self.op in ("add", "sub", "mul", "div") else 1
        if len(self.args) != arity:
            raise ValueError("wrong operator arity")
        if (self.op == "const") != (self.value is not None):
            raise ValueError("value only for const")
        if self.value is not None and (not math.isfinite(self.value) or abs(self.value) > 1e9):
            raise ValueError("constant bound")
        if (self.op == "field") != (self.field is not None):
            raise ValueError("field only for field")
        if (self.op in ("lag", "sma", "std", "min", "max", "return")) != (self.window is not None):
            raise ValueError("window required only for rolling/lag/return")
        return self


class Condition(Strict):
    left: Expr
    cmp: Literal["gt", "lt", "ge", "le", "cross_above", "cross_below"]
    right: Expr


class Evidence(Strict):
    rule: Literal["entry", "exit", "universe", "timeframe", "sizing", "costs", "execution"]
    label: Literal["explicit in source", "declared assumption", "unresolved/unsupported"]
    detail: str = Field(min_length=1, max_length=1000)
    quote: str = Field(default="", max_length=240)


class Spec(Strict):
    formulation: Literal["source_interpretation", "llm_hypothesis"] = "source_interpretation"
    name: str = Field(min_length=1, max_length=120)
    status: Literal[
        "runnable", "interpretation", "needs clarification", "unsupported", "rejected as non-strategy"
    ]
    family: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,9}$")
    universe: list[str] = Field(default_factory=list, max_length=50)
    max_positions: int = Field(default=1, ge=1, le=50)
    max_total_fraction: float = Field(default=1.0, gt=0, le=1)
    ranking: Expr | None = None
    rank_order: Literal["highest", "lowest"] = "highest"
    rebalance: Literal["signals", "session_open", "month_open"] = "signals"
    entry_logic: Literal["all", "any"] = "all"
    exit_logic: Literal["all", "any"] = "all"
    timeframe: Literal["1min", "5min", "15min", "30min", "1h", "1d"]
    entry: list[Condition] = Field(max_length=8)
    exit: list[Condition] = Field(default_factory=list, max_length=8)
    exit_next_session_open: bool = False
    execution: Literal["next_bar_open"] = "next_bar_open"
    position_fraction: float = Field(gt=0, le=1)
    fee_bps: float = Field(ge=0, le=100)
    slippage_bps: float = Field(ge=0, le=500)
    ambiguities: list[str] = Field(max_length=30)
    evidence: list[Evidence] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def constraints(self):
        if len(set(self.universe)) != len(self.universe) or any(
            not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", s) for s in self.universe
        ):
            raise ValueError("invalid or duplicate universe symbols")
        if self.universe and self.symbol not in self.universe:
            raise ValueError("primary symbol must belong to universe")
        if self.max_positions > len(self.universe or [self.symbol]):
            raise ValueError("position count exceeds supplied universe")
        nodes = 0

        def walk(e, depth=0):
            nonlocal nodes
            nodes += 1
            if depth > 10 or nodes > 200:
                raise ValueError("expression resource limit")
            for child in e.args:
                walk(child, depth + 1)

        if self.ranking is not None:
            walk(self.ranking)
        for c in self.entry + self.exit:
            walk(c.left)
            walk(c.right)
        if self.formulation == "llm_hypothesis" and self.status == "runnable":
            raise ValueError("hypotheses must disclose interpretation status")
        if self.status in ("runnable", "interpretation"):
            if not self.entry:
                raise ValueError("runnable strategy needs entry conditions")
            if self.exit_next_session_open and self.timeframe == "1d":
                raise ValueError("pre-close overnight entry requires intraday data")
            if not self.exit and not self.exit_next_session_open:
                raise ValueError("missing exit")
            if {e.rule for e in self.evidence} != {
                "entry",
                "exit",
                "universe",
                "timeframe",
                "sizing",
                "costs",
                "execution",
            }:
                raise ValueError("every rule category requires evidence")
            if any(e.label == "unresolved/unsupported" for e in self.evidence):
                raise ValueError("unresolved critical rule cannot run")
            if self.status == "runnable" and any(e.label != "explicit in source" for e in self.evidence):
                raise ValueError("assumptions require interpretation status")
            if self.ambiguities:
                raise ValueError("unresolved ambiguity cannot run")
        return self


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, allow_nan=False).encode()).hexdigest()
