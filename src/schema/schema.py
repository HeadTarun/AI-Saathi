from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    key: str = Field(description="Agent key.")
    description: str = Field(description="Description of the agent.")

