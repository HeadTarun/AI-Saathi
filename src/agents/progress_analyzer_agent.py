from agents.local_agents import ProgressAgent


progress_analyzer = ProgressAgent()


async def run_progress_analysis(user_id: str) -> dict:
    return progress_analyzer.process({"user_id": user_id}, "get_progress")
