from agents.local_agents import BaseLocalAgent, RouterAgent, run_agent_task
from agents.planner_agent import planner_agent
from agents.progress_analyzer_agent import progress_analyzer
from agents.quiz_agent import quiz_agent
from agents.teacher_agent import teacher_agent
from schema.schema import AgentInfo

DEFAULT_AGENT = "study-router"


class Agent:
    def __init__(self, description: str, graph_like: BaseLocalAgent) -> None:
        self.description = description
        self.graph_like = graph_like


router_agent = RouterAgent(
    {
        "study-planner": planner_agent,
        "study-teacher": teacher_agent,
        "study-quiz": quiz_agent,
        "study-progress": progress_analyzer,
    }
)

AGENTS: dict[str, Agent] = {
    "study-router": Agent(
        description="Routes all study requests to the appropriate task agent.",
        graph_like=router_agent,
    ),
    "study-planner": Agent(
        description="Creates or adjusts AI Study Companion study plans.",
        graph_like=planner_agent,
    ),
    "study-teacher": Agent(
        description="Teaches a study plan day with grounded RAG content.",
        graph_like=teacher_agent,
    ),
    "study-quiz": Agent(
        description="Generates and scores AI Study Companion quizzes.",
        graph_like=quiz_agent,
    ),
    "study-progress": Agent(
        description="Updates quiz performance, weak areas, and replan flags.",
        graph_like=progress_analyzer,
    ),
}


def get_all_agent_info() -> list[AgentInfo]:
    return [
        AgentInfo(key=agent_id, description=agent.description)
        for agent_id, agent in AGENTS.items()
    ]


def run_study_task(task: str, **payload):
    return run_agent_task(router_agent, task, **payload)

