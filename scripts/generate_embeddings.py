"""为图谱中所有节点生成 embedding 向量，并添加 :Entity 标签。

前置条件：
- Neo4j 容器运行中
- embedding API 可访问（通过 GraphVI 设置的配置）
"""
import os
import sys

from neo4j import GraphDatabase
from openai import OpenAI


def _get_embedding(client, model: str, text: str) -> list[float]:
    if not text.strip():
        text = "(empty)"
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


def _build_text(node: dict) -> str:
    """将所有字段拼接为文本用于向量化，排除 id/embedding 等字段。"""
    parts = []
    skip_keys = {"elementId", "embedding", "id", "Id"}
    for k, v in node.items():
        if k in skip_keys or k.startswith("_"):
            continue
        if v is None:
            continue
        val = str(v).strip()
        if val and val not in ("None", ""):
            parts.append(val)
    return " ".join(parts)


def run(neo4j_uri: str, neo4j_user: str, neo4j_pwd: str, database: str,
        emb_endpoint: str, emb_api_key: str, emb_model: str, emb_dims: int):

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pwd))
    client = OpenAI(api_key=emb_api_key, base_url=emb_endpoint.rstrip("/") + "/")

    # 1. 创建 Entity 标签的唯一约束（可选，避免重复）
    with driver.session(database=database) as session:
        session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.elementId IS UNIQUE")

    # 2. 获取所有节点
    with driver.session(database=database) as session:
        result = session.run("MATCH (n) RETURN n, elementId(n) AS eid, labels(n) AS labels")
        rows = list(result)
    print(f"共 {len(rows)} 个节点")

    # 3. 逐节点生成 embedding
    count = 0
    batch = []
    for record in rows:
        node = record["n"]
        eid = record["eid"]
        labels = record["labels"]

        text = _build_text(dict(node))
        vec = _get_embedding(client, emb_model, text)
        batch.append((eid, labels, vec))
        count += 1

        if count % 50 == 0:
            print(f"  → {count}/{len(rows)}")

    # 4. 批量写入
    print(f"写入 {len(batch)} 个节点的 embedding...")
    with driver.session(database=database) as session:
        for eid, labels, vec in batch:
            session.run("""
                MATCH (n) WHERE elementId(n) = $eid
                SET n:Entity, n.embedding = $vec
            """, eid=eid, vec=vec)
    print("写入完成")

    # 5. 创建向量索引
    dims = emb_dims
    with driver.session(database=database) as session:
        session.run("""
            CREATE VECTOR INDEX entity_vector IF NOT EXISTS
            FOR (n:Entity) ON (n.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: $dims,
                `vector.similarity_function`: 'cosine'
            }}
        """, dims=dims)
    print(f"向量索引已创建，维度 {dims}")
    print("全部完成！")
    driver.close()


if __name__ == "__main__":
    # ─── 配置 ───────────────────────────────────────────
    # 从环境变量读取，也支持直接修改
    run(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_pwd=os.getenv("NEO4J_PWD", "password123"),
        database=os.getenv("NEO4J_DB", "neo4j"),
        emb_endpoint=os.getenv("EMB_ENDPOINT", "http://localhost:8000/v1"),
        emb_api_key=os.getenv("EMB_API_KEY", ""),
        emb_model=os.getenv("EMB_MODEL", "Qwen/Qwen3-Embedding-4B"),
        emb_dims=int(os.getenv("EMB_DIMS", "2560")),
    )
