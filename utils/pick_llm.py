"""
during the flow we need LLM with different roles with different capacities to perform the different task.
"""

from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

def pick_llm(level: str):
    """
    picks the appropriate LLM based on the level of question.

    Args:
        level: the level of the question, can be "easy", "medium" or "hard"

    Returns:
        str: the name of the llm to be used.
    """

    if level.lower() == "low":
        llm = ChatGroq(model="openai/gpt-oss-20b")
    elif level.lower() == "medium":
        llm = ChatGroq(model="openai/gpt-oss-120b")
    elif level.lower() == "hard":
        llm = ChatGroq(model="openai/gpt-oss-120b")
    else:
        raise ValueError(f"Unsupported level: {level}")

    return llm

if __name__ == "__main__":
    llm_obj = pick_llm("low")
    print(llm_obj.invoke("capital of india?"))