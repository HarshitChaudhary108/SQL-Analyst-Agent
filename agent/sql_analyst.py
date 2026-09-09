import os
import psycopg2
import psycopg2.extras
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from utils.database import DatabaseUtil
from agent_schema.schema import AgentSchema, JudgeSchema
from utils.pick_llm import pick_llm
from langgraph.graph import StateGraph, START, END

#--------------------------------------------AI Agent Code---------------------------------------

def curate_question_node(state: AgentSchema) -> AgentSchema:
    user_question = state["user_question"]
    llm = pick_llm("low")
    response = llm.invoke(f"curate the following question: {user_question}")
    state["curated_ques"] = response.content
    state["messages"] = [HumanMessage(content=f"{response}")] 
    return state

def prompt_query_node(state: AgentSchema) -> AgentSchema:
    curated_question = state["curated_ques"]
    conn_details = {
        "host": os.environ["host"],
        "password": os.environ["password"],
        "port": os.environ["port"],
        "user": os.environ["user"],
        "database": os.environ["database"]
    }
    db_obj = DatabaseUtil(conn_details)
    schema_info = db_obj.schema_details(schema_name="public")
    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language
    query into Postgres SQL query that can be executed on the database. You are provided
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.

    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}
    """

    state["prompt_query"] = prompt

    return state



def generate_sql_query_node(state: AgentSchema) -> AgentSchema:
    prompt = state["prompt_query"]
    llm = pick_llm("hard")
    generated_sql_query = llm.invoke(prompt)

    state["generated_sql_query"] = generated_sql_query.content

    return state


# Is Safe Node
def is_safe_node(state: AgentSchema) -> AgentSchema:
    sql_query = state["generated_sql_query"]
    llm = pick_llm("hard")
    
    prompt = f"""
    You are an SQL Judge for data security. Determine whether the SQL query is
    safe or not. The SQL query should only be used for data retrieval and should not modify
    the database in any way (no INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, etc).

    Respond ONLY in JSON with this exact structure:
    {{
        "answer": "Yes" or "No",
        "comment": "<reason for your judgement>"
    }}

    Here's the SQL query to evaluate:
    {sql_query}
    """

    judge_llm = llm.with_structured_output(JudgeSchema, method="json_schema")
    response = judge_llm.invoke(prompt).model_dump()
    state["is_safe"] = response["answer"]
    state["comments"] = response["comment"]
    return state


# Canceled SQL Query Node
def canceled_sql_query_node(state: AgentSchema) -> AgentSchema:
    comments = state["comments"]
    state["final_answer"] = f"The generated SQL query is not safe to execute. Reason: {comments}"

    return state


# Execute SQL Query Node
def execute_sql_query_node(state: AgentSchema) -> AgentSchema:
    sql_query = state["generated_sql_query"]
    conn_details = {
        "host": os.environ["host"],
        "password": os.environ["password"],
        "port": os.environ["port"],
        "user": os.environ["user"],
        "database": os.environ["database"]
    }

    conn = None
    cursor = None
    try:
        db_obj = DatabaseUtil(conn_details)
        conn= db_obj.conn
        cursor=conn.cursor(cursor_factory= psycopg2.extras.RealDictCursor)
        cursor.execute(sql_query)
        result = cursor.fetchall()

        state["sql_execution_result"] = result

    except Exception as e:
        state["sql_execution_result"] = f"Error occurred while executing SQL query: {e}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return state


# forwarding the final answer to the user
def represent_final_answer(state: AgentSchema) -> AgentSchema:
    execution_result = state["sql_execution_result"]
    curated_question = state["curated_ques"]

    llm = pick_llm("medium")

    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer.
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """

    llm_response = llm.invoke(prompt).content  # Get the final answer from the LLM

    state["final_answer"] = llm_response
    state["messages"] = state["messages"] + [AIMessage(content=f"{llm_response}")]  # Append the final answer to the messages list

    return state



#---------------------------------------------Graph Building--------------------------------------
sql_analyst_graph = StateGraph(AgentSchema)

# Nodes
sql_analyst_graph.add_node("curate_question", curate_question_node)
sql_analyst_graph.add_node("generate_sql_query", generate_sql_query_node)
sql_analyst_graph.add_node("prompt_query", prompt_query_node)
sql_analyst_graph.add_node("is_safe", is_safe_node)
sql_analyst_graph.add_node("canceled_sql_query", canceled_sql_query_node)
sql_analyst_graph.add_node("execute_sql_query", execute_sql_query_node)
sql_analyst_graph.add_node("represent_final_answer", represent_final_answer)

# edges
sql_analyst_graph.add_edge(START, "curate_question")
sql_analyst_graph.add_edge("curate_question", "prompt_query")
sql_analyst_graph.add_edge("prompt_query", "generate_sql_query")
sql_analyst_graph.add_edge("generate_sql_query", "is_safe")

def is_safe_edge_condition(state: AgentSchema) -> str:
    return "execute_query" if state["is_safe"].lower() == "yes" else "cancel_query"

sql_analyst_graph.add_conditional_edges("is_safe", is_safe_edge_condition, {
    "execute_query": "execute_sql_query",
    "cancel_query": "canceled_sql_query"
})
sql_analyst_graph.add_edge("execute_sql_query", "represent_final_answer")
sql_analyst_graph.add_edge("canceled_sql_query", "represent_final_answer")
sql_analyst_graph.add_edge("represent_final_answer", END)

sql_analyst = sql_analyst_graph.compile()

if __name__ == "__main__":
    initial_state = {
        "messages": [],
        "user_question": "total payments done where user id is '5455'?",
        "curated_ques": "",
        "prompt_query": "",
        "is_safe": "",
        "generated_sql_query": "",
        "comments": "",
        "sql_execution_result": "",
        "final_answer": ""
    }

    final_state = sql_analyst.invoke(initial_state)
    print(final_state["final_answer"])
    print(final_state["generated_sql_query"])
    print(final_state["sql_execution_result"])