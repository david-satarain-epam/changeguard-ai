"""Tools for multiagent systems support agent."""

import os

import dotenv
from google import genai
from google.adk.tools import BaseTool
from google.adk.tools import ToolContext
from google.cloud import bigquery


LOCATION = os.environ["GOOGLE_CLOUD_LOCATION"]

# --- Callback Tool Guardrail for Security ---
async def validate_tool_params(
    tool: BaseTool,
    args: dict,
    tool_context: ToolContext,
) -> dict | None:
  """Callback hook that acts as a security guardrail before any tool executes.

  Blocks queries that might contain sensitive developer secrets or credentials.

  Args:
    tool: The tool instance being called.
    args: The arguments passed to the tool.
    tool_context: The context for the tool execution.

  Returns:
    A dict containing an error response if blocked, otherwise None.
  """
  tool_name = tool.name
  args_str = str(args).lower()

  sensitive_keywords = [
      "private_key",
      "aws_key",
      "gcp_key",
      "token",
      "password",
      "client_secret",
  ]

  if any(kw in args_str for kw in sensitive_keywords):
    print(
        "\n[SECURITY GUARDRAIL] Blocked tool call to"
        f" '{tool_name}' containing sensitive terms."
    )
    return {
        "error": (
            "Tool call blocked: Query parameters contain sensitive keywords"
            " (credentials, keys, or secrets)."
        )
    }
  return None


def find_similar_bugs(clean_query: str) -> str:
  """Performs a semantic search in the BigQuery bug database to find bugs.

  Args:
    clean_query: The description of the new bug to search for.

  Returns:
    A formatted string of the top 3 most similar bugs found, or a message
    if no similar bugs are found.
  """
  dotenv.load_dotenv()

  project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "whistle-flow-demo")
  dataset = os.environ.get("BIGQUERY_DATASET", "ops_intelligence")
  table = os.environ.get("BIGQUERY_TABLE", "incident_post_mortems")

  print(
      "TOOL: Received search query for BigQuery vector search:"
      f" '{clean_query}'"
  )

  try:
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=LOCATION
    )

    response = client.models.embed_content(
        model="text-embedding-004",
        contents=clean_query
    )

    query_embedding = response.embeddings[0].values
  except Exception as e:
    return (
        "[System Notice: The Text Embedding Service is temporarily unavailable."
        " Unable to calculate query embeddings. Please proceed using other"
        " available documentation channels only.]"
    )

  sql_query = f"""
  SELECT
    base.title,
    base.description,
    distance
  FROM
    VECTOR_SEARCH(
      TABLE `{project_id}.{dataset}.{table}`,
      'description_embedding',
      (SELECT @query_embedding AS embedding),
      top_k => 3,
      distance_type => 'COSINE'
    )
  """

  # Initialize BigQuery client
  bq_client = bigquery.Client(project=project_id)
  job_config = bigquery.QueryJobConfig(
      query_parameters=[
          bigquery.ArrayQueryParameter(
              "query_embedding", "FLOAT64", query_embedding
          ),
      ]
  )

  try:
    query_job = bq_client.query(sql_query, job_config=job_config)
    results = query_job.result()
  except Exception as e:
    return (
        "[System Notice: The BigQuery similar bugs search database is"
        " temporarily offline or inaccessible. Please proceed using other"
        " available documentation channels only.]"
    )

  if results.total_rows == 0:
    return "No similar bugs were found in the database."

  response_parts = ["Found similar bugs:\n"]
  for i, row in enumerate(results):
    response_parts.append(
        f"{i+1}. Title: {row.title}\n"
        f"   Description: {row.description}\n"
        f"   (Similarity Score/Distance: {row.distance:.4f})\n"
    )

  return "\n".join(response_parts)
