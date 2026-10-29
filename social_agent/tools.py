"""Minimal schema-validated, bounded, explicit tools.

No arbitrary Python evaluation and no unaudited outbound web requests.
"""

import ast
import asyncio
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError


class CalculatorArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=100)


class TimeArgs(BaseModel):
    timezone_name: str = Field(default="UTC", pattern=r"^UTC$")


def _evaluate(node: ast.AST, depth: int = 0) -> float:
    if depth > 12:
        raise ValueError("Expression too deep")
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, depth + 1)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand, depth + 1)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _evaluate(node.left, depth + 1), _evaluate(node.right, depth + 1)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        else:
            if right == 0:
                raise ValueError("Division by zero")
            result = left / right
        if abs(result) > 1e12:
            raise ValueError("Result exceeds safety limit")
        return result
    raise ValueError("Only numeric literals and + - * / parentheses are allowed")


def safe_calculate(expression: str) -> str:
    args = CalculatorArgs(expression=expression)
    tree = ast.parse(args.expression, mode="eval")
    result = _evaluate(tree)
    return f"{result:g}"


async def invoke_tool(command: str, timeout_s: float = 2.0) -> tuple[str, str]:
    """Invoke registered tool with timeout. The command is explicit user syntax."""

    async def run() -> tuple[str, str]:
        if command.startswith("@calc "):
            expression = command.removeprefix("@calc ").strip()
            try:
                return "calculator", await asyncio.to_thread(safe_calculate, expression)
            except (ValueError, SyntaxError, ValidationError, OverflowError, ZeroDivisionError) as exc:
                return "calculator", f"Tool error: {exc}"
        if command.strip() == "@time":
            TimeArgs(timezone_name="UTC")
            return "utc_time", datetime.now(timezone.utc).isoformat()
        return "unknown", "Tool error: unknown command"

    return await asyncio.wait_for(run(), timeout=timeout_s)
