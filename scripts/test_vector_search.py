# -*- coding: utf-8 -*-
"""向量检索测试脚本。

用法:
    python scripts/test_vector_search.py "查询巴威台风相关的事件"
    python scripts/test_vector_search.py "某问题" --top_k 20 --threshold 0.5

输出: 向量匹配候选、分数分布、threshold/top_k 过滤结果。
读取 settings_db 配置（embedding API、Neo4j、vector_index、semantic_top_k、threshold）。
"""

import sys
import io
import time
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\project\sjzl\graphvi\backend")

from settings_db import get_all_settings
from semantic_search import _get_embedder
from nl2cypher import _get_cached_driver
from neo4j_graphrag.retrievers import VectorRetriever


def _node_name(node: dict) -> str:
    """Extract a display name from a node's properties."""
    for k in ("event_name", "person_name", "equipment_name", "vehicle_name",
              "name", "title", "work_order_name", "apply_person", "contact_person"):
        v = node.get(k)
        if v:
            return str(v)
    return "?"


def main(question: str, top_k: int | None = None, threshold: float | None = None):
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")
    index_name = s.get("vector_index_name", "entity_vector")

    if top_k is None:
        top_k = int(s.get("semantic_top_k", "10"))
    if threshold is None:
        threshold = float(s.get("semantic_score_threshold", "0.6"))

    embedder = _get_embedder()
    driver = _get_cached_driver(uri, user, pwd)
    retriever = VectorRetriever(driver=driver, index_name=index_name, embedder=embedder)

    t0 = time.monotonic()
    raw = retriever.get_search_results(query_text=question, top_k=max(top_k, 100))
    elapsed = time.monotonic() - t0

    # 收集候选（node 为 dict 且非空的）
    candidates = []
    for rec in raw.records:
        score = rec.get("score", 0)
        node = rec.get("node", {})
        node_labels = rec.get("nodeLabels", [])
        eid = rec.get("elementId", "")
        if isinstance(node, dict) and node:
            uid = str(node.get("id", eid))
            candidates.append({
                "score": score,
                "id": uid,
                "labels": list(node_labels),
                "name": _node_name(node),
            })

    candidates.sort(key=lambda c: c["score"], reverse=True)

    print(f"问题: {question}")
    print(f"配置: top_k={top_k}  threshold={threshold}  index={index_name}  neo4j={uri}")
    print(f"检索耗时: {elapsed:.2f}s   候选总数: {len(candidates)}")
    if candidates:
        print(f"分数范围: {candidates[-1]['score']:.4f} ~ {candidates[0]['score']:.4f}")

        passed = [c for c in candidates if c["score"] >= threshold]
        print(f"threshold={threshold} 过滤后: {len(passed)}/{len(candidates)}")
        print(f"top_k={top_k} 截断后: {min(len(passed), top_k)} 个 entry")
    else:
        print("（无候选）")
        return

    print("\n=== 匹配结果 ===")
    for i, c in enumerate(candidates[:top_k], 1):
        flag = "✓" if c["score"] >= threshold else "✗"
        print(f"{flag} {i:>3}. score={c['score']:.4f}  {c['name'][:25]:25s} labels={c['labels']}")
        print(f"       id={c['id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试向量检索")
    parser.add_argument("question", help="查询问题")
    parser.add_argument("--top_k", type=int, default=None, help="返回数量（默认用设置 semantic_top_k）")
    parser.add_argument("--threshold", type=float, default=None, help="分数阈值（默认用设置 semantic_score_threshold）")
    args = parser.parse_args()
    main(args.question, args.top_k, args.threshold)
