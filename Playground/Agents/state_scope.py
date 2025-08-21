
# """
# State Definitions and Pydantic Schemas for Research Agent

# This module defines the state objects and structured schemas used for
# the research agent workflow, including researcher state management and output schemas.
# """

# import operator
# from typing_extensions import TypedDict, Annotated, List, Sequence
# from pydantic import BaseModel, Field
# from langchain_core.messages import BaseMessage
# from langgraph.graph.message import add_messages

# # ===== STATE DEFINITIONS =====

# class ResearcherState(TypedDict):
#     """
#     State for the research agent containing message history and research metadata.

#     This state tracks the researcher's conversation, iteration count for limiting
#     tool calls, the research topic being investigated, compressed findings,
#     and raw research notes for detailed analysis.
#     """
#     researcher_messages: Annotated[Sequence[BaseMessage], add_messages]
#     tool_call_iterations: int
#     research_topic: str
#     compressed_research: str
#     raw_notes: Annotated[List[str], operator.add]

# class ResearcherOutputState(TypedDict):
#     """
#     Output state for the research agent containing final research results.

#     This represents the final output of the research process with compressed
#     research findings and all raw notes from the research process.
#     """
#     compressed_research: str
#     raw_notes: Annotated[List[str], operator.add]
#     researcher_messages: Annotated[Sequence[BaseMessage], add_messages]

# # ===== STRUCTURED OUTPUT SCHEMAS =====

# class ClarifyWithUser(BaseModel):
#     """Schema for user clarification decisions during scoping phase."""
#     need_clarification: bool = Field(
#         description="Whether the user needs to be asked a clarifying question.",
#     )
#     question: str = Field(
#         description="A question to ask the user to clarify the report scope",
#     )
#     verification: str = Field(
#         description="Verify message that we will start research after the user has provided the necessary information.",
#     )

# class ResearchQuestion(BaseModel):
#     """Schema for research brief generation."""
#     research_brief: str = Field(
#         description="A research question that will be used to guide the research.",
#     )

# class Summary(BaseModel):
#     """Schema for webpage content summarization."""
#     summary: str = Field(description="Concise summary of the webpage content")
#     key_excerpts: str = Field(description="Important quotes and excerpts from the content")



"""State Definitions and Pydantic Schemas for Research Scoping.

This defines the state objects and structured schemas used for
the research agent scoping workflow, including researcher state management and output schemas.
"""

import operator
from typing_extensions import Optional, Annotated, List, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# ===== STATE DEFINITIONS =====

class AgentInputState(MessagesState):
    """Input state for the full agent - only contains messages from user input."""
    pass

class AgentState(MessagesState):
    """
    Main state for the full multi-agent research system.

    Extends MessagesState with additional fields for research coordination.
    Note: Some fields are duplicated across different state classes for proper
    state management between subgraphs and the main workflow.
    """

    # Research brief generated from user conversation history
    research_brief: Optional[str]
    # Messages exchanged with the supervisor agent for coordination
    supervisor_messages: Annotated[Sequence[BaseMessage], add_messages]
    # Raw unprocessed research notes collected during the research phase
    raw_notes: Annotated[list[str], operator.add] = []
    # Processed and structured notes ready for report generation
    notes: Annotated[list[str], operator.add] = []
    # Final formatted research report
    final_report: str

# ===== STRUCTURED OUTPUT SCHEMAS =====

class ClarifyWithUser(BaseModel):
    """Schema for user clarification decision and questions."""

    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )

class ResearchQuestion(BaseModel):
    """Schema for structured research brief generation."""

    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )
