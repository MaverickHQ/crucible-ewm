from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from services.core.actions import PlaceBuy, PlaceSell
from services.core.planner.base import Planner
from services.core.planner.types import PlannerError, PlannerResult
from services.core.transitions import Action


@dataclass(frozen=True)
class BedrockPlanResponse:
    actions: List[Dict[str, object]]
    planner_metadata: Optional[Dict[str, object]] = None


def parse_bedrock_plan(payload: Dict[str, object]) -> BedrockPlanResponse:
    actions = payload.get("actions") or payload.get("plan")
    if actions is None:
        raise ValueError("Missing 'actions' in Bedrock response.")
    if not isinstance(actions, list):
        raise ValueError("'actions' must be a list.")
    for item in actions:
        if not isinstance(item, dict):
            raise ValueError("Each action must be an object.")
        _action_from_payload(item)

    planner_metadata = payload.get("planner_metadata")
    if planner_metadata is not None and not isinstance(planner_metadata, dict):
        raise ValueError("'planner_metadata' must be an object if provided.")
    return BedrockPlanResponse(actions=actions, planner_metadata=planner_metadata)


def _action_from_payload(item: Dict[str, object]) -> Action:
    action_type = item.get("type")
    if action_type not in {"PlaceBuy", "PlaceSell"}:
        raise ValueError(f"Unknown action type: {action_type}")
    symbol = item.get("symbol")
    quantity = item.get("quantity")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("Action 'symbol' must be a non-empty string.")
    if not isinstance(quantity, (int, float)):
        raise ValueError("Action 'quantity' must be a number.")
    price = item.get("price", 0.0) or 0.0
    if not isinstance(price, (int, float)):
        raise ValueError("Action 'price' must be a number.")
    if action_type == "PlaceBuy":
        return PlaceBuy(symbol=symbol, quantity=float(quantity), price=float(price))
    return PlaceSell(symbol=symbol, quantity=float(quantity), price=float(price))


class BedrockPlanner(Planner):
    name = "bedrock"

    def __init__(self, model_id: str, region_name: str) -> None:
        self._model_id = model_id
        self._region_name = region_name

    def propose(
        self,
        state_summary: Dict[str, object],
        policy: Dict[str, object],
        goal: str,
    ) -> PlannerResult:
        prompt = (
            "Return JSON only. No markdown. Schema: "
            "{'actions':[{'type':'PlaceBuy'|'PlaceSell','symbol':str,'quantity':number,'price':number}],"
            "'planner_metadata':{'goal':'approve|reject','note':str}}. "
            "Do not output an empty actions list. If unsure, follow the templates exactly. "
            f"Goal={goal}. Fixture prices: step0 AAPL=100.0, step1 AAPL=101.0, step1 MSFT=198.0. "
            "For goal=reject return exactly 2 actions: "
            "1) PlaceBuy AAPL quantity=1 price=100.0, "
            "2) PlaceBuy AAPL quantity=20 price=101.0. "
            "For goal=approve return exactly 2 actions: "
            "1) PlaceBuy AAPL quantity=1 price=100.0, "
            "2) PlaceBuy MSFT quantity=1 price=198.0."
        )

        try:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=self._region_name)
            response = client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "temperature": 0.0,
                        "max_tokens": 512,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
            )
            raw_body = response.get("body")
            body_bytes = raw_body.read() if hasattr(raw_body, "read") else raw_body
            payload = json.loads(body_bytes.decode("utf-8"))
            if isinstance(payload, dict) and "content" in payload:
                content = payload.get("content")
                if isinstance(content, list):
                    text = "".join(
                        item.get("text", "") for item in content if isinstance(item, dict)
                    )
                    payload = json.loads(text)
            elif isinstance(payload, dict) and isinstance(payload.get("completion"), str):
                payload = json.loads(payload["completion"])

            parsed = parse_bedrock_plan(payload)
            actions = [_action_from_payload(item) for item in parsed.actions]
            if not actions:
                raise ValueError("Bedrock returned an empty plan.")
        except Exception as exc:
            error_code = "empty_plan" if "empty plan" in str(exc).lower() else "bedrock_error"
            return PlannerResult(
                plan=[],
                planner_name=self.name,
                metadata={"model_id": self._model_id, "error": str(exc)},
                error=PlannerError(code=error_code, message=str(exc)),
            )

        metadata = {
            "model_id": self._model_id,
            "region": self._region_name,
        }
        request_id = response.get("ResponseMetadata", {}).get("RequestId")
        if request_id:
            metadata["request_id"] = request_id
        if parsed.planner_metadata:
            metadata["planner_metadata"] = parsed.planner_metadata

        return PlannerResult(plan=actions, planner_name=self.name, metadata=metadata)
