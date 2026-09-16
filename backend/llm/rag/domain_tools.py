"""RAG 도메인별 서버 allowlist와 bounded tool 실행."""

import json

from langchain_core.messages import ToolMessage

from ..tools import create_domain_tools


DOMAIN_TOOLS = {
    "club": frozenset({
        "get_standings", "get_games", "search_players", "get_ticket_prices",
        "get_ticket_policies", "get_seat_zones", "get_seat_views", "get_seat_maps",
        "search_community_posts", "get_prediction_games",
    }),
    "venue": frozenset({
        "search_places", "get_facilities", "get_food_stores", "get_transport",
        "get_stadium", "get_stadium_contents",
    }),
    "course": frozenset({
        "search_places", "get_directions", "search_tourism", "get_weather", "get_games",
        "get_stadium", "get_stadium_contents", "search_courses", "get_course",
    }),
}


def tools_for(domain):
    allowed = DOMAIN_TOOLS[domain]
    return tuple(tool for tool in create_domain_tools() if tool.name in allowed)


def invoke(domain, name, arguments):
    if name not in DOMAIN_TOOLS[domain]:
        raise ValueError(f"{name} is not allowed for {domain}")
    tool = next(tool for tool in tools_for(domain) if tool.name == name)
    return tool.invoke(arguments)


def run_model(model, messages, domain, max_tool_rounds=2, tool_names=None, require_first_tool=False):
    """허용 도구만 노출하고, 도구 결과를 다음 모델 호출에 넣어 유한 횟수로 답한다."""
    tools = tools_for(domain)
    if tool_names is not None:
        requested = frozenset(tool_names)
        if not requested <= DOMAIN_TOOLS[domain]:
            raise ValueError(f"tools are not allowed for {domain}")
        tools = tuple(tool for tool in tools if tool.name in requested)
    allowed = {tool.name: tool for tool in tools}
    bound = model.bind_tools(tools)
    first = model.bind_tools(tools, tool_choice="required") if require_first_tool else bound
    conversation = list(messages)
    for round_number in range(max_tool_rounds):
        response = (first if round_number == 0 else bound).invoke(conversation)
        conversation.append(response)
        if not response.tool_calls:
            return response
        for call in response.tool_calls:
            tool = allowed.get(call["name"])
            result = tool.invoke(call["args"]) if tool else "허용되지 않은 도구입니다."
            conversation.append(ToolMessage(
                content=json.dumps(result, ensure_ascii=False, default=str),
                tool_call_id=call["id"], name=call["name"],
            ))
    return model.invoke(conversation)
