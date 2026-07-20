from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langgraph.graph import START
from state import State, graph_builder
from langchain_tavily import TavilySearch
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt

api_key = "sk-cp-cLMZQs9GoZlEMSB13KHy1AgVQaWFxv3y_NrjGcAuofOccNRM7Pec1o-tWLAgE6A0ZpMNsuC1_v-jHsTDo9CF2XeOV1_Z7CEP8q-q_LfAafLOLZxpwM4jxTs"
tavily_api_key = "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"

llm = init_chat_model(
    "MiniMax-M3",
    model_provider="openai",
    api_key=api_key,
    base_url="https://api.minimaxi.com/v1",
)

@tool
def human_assistance(query: str) -> str:
    """当用户明确要求人工处理、人工确认、人工审核，或模型无法可靠回答时，必须调用此工具。请详细描述问题，并等待人工回复。"""
    human_response = interrupt({"query": query})
    return human_response["data"]

tool = TavilySearch(tavily_api_key=tavily_api_key, max_results=3)
tools = [tool, human_assistance]
llm_with_tools = llm.bind_tools(tools)

memory = MemorySaver()

def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools=tools))
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
graph_builder.add_edge("tools", "chatbot")


graph_builder.add_edge(START, "chatbot")
graph = graph_builder.compile(checkpointer=memory)



def print_events(events):
    for event in events:
        for value in event.values():
            if isinstance(value, dict) and value.get("messages"):
                message = value["messages"][-1]
                if message.type == "ai" and message.content:
                    print("Assistant:", message.content)


def stream_graph_updates(user_input: str):
    config = {"configurable": {"thread_id": "2"}}
    events = graph.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
    )

    while True:
        print_events(events)

        snapshot = graph.get_state(config)
        interrupts = [
            item
            for task in snapshot.tasks
            for item in task.interrupts
        ]
        if not interrupts:
            break

        request = interrupts[0].value
        query = request.get("query", request) if isinstance(request, dict) else request
        print("需要人工协助：", query)
        human_response = input("Human: ")
        events = graph.stream(
            Command(resume={"data": human_response}),
            config,
        )

def main():
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            stream_graph_updates(user_input)
        except EOFError:
            # fallback if input() is not available
            user_input = "What do you know about LangGraph?"
            print("User: " + user_input)
            stream_graph_updates(user_input)
            break
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
