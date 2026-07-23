# -*- coding: utf-8 -*-
import os
from neo4j import GraphDatabase
from openai import OpenAI

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
pwd = os.getenv("NEO4J_PWD", "password123")
api_key = os.getenv("EMB_API_KEY", "")
model = os.getenv("EMB_MODEL", "Qwen/Qwen3-Embedding-4B")
dims = int(os.getenv("EMB_DIMS", "2560"))
limit = int(os.getenv("LIMIT", "0"))

driver = GraphDatabase.driver(uri, auth=("neo4j", pwd))
client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")

driver.execute_query("MATCH (n:Movie) SET n:Entity")
print("[OK] Entity label added")

limit_str = ""
if limit:
    limit_str = " LIMIT " + str(limit)

rows = driver.execute_query(
    "MATCH (n:Movie) RETURN n, elementId(n) AS eid" + limit_str,
    result_transformer_=lambda r: list(r),
)
print("[DATA] " + str(len(rows)) + " Movie nodes")

for i, record in enumerate(rows):
    node = record["n"]
    eid = record["eid"]
    props = dict(node)
    props.pop("embedding", None)
    text = " ".join(str(v) for v in props.values() if v is not None)
    resp = client.embeddings.create(model=model, input=text)
    driver.execute_query(
        "MATCH (n) WHERE elementId(n) = $eid SET n.embedding = $vec",
        eid=eid, vec=resp.data[0].embedding,
    )
    if (i + 1) % 50 == 0:
        print("  -> " + str(i+1) + "/" + str(len(rows)))

create_index = (
    "CREATE VECTOR INDEX entity_vector IF NOT EXISTS "
    "FOR (n:Entity) ON (n.embedding) "
    "OPTIONS {indexConfig: {"
    "`vector.dimensions`: " + str(dims) + ", "
    "`vector.similarity_function`: 'cosine'"
    "}}"
)
driver.execute_query(create_index)
print("[OK] Vector index created")
print("[DONE] All done")
driver.close()
