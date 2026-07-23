# 向量索引验证记录

验证 `graphvi-neo4j-apoc` 镜像中的 Neo4j 版本是否支持向量索引。

## 环境

| 项目 | 值 |
|------|-----|
| 基础镜像 | `neo4j:5` |
| 构建镜像 | `graphvi-neo4j-apoc:5` |
| Neo4j 版本 | 5.26.26 |
| 插件 | APOC (`apoc.jar`) |
| 端口 | 7474 (HTTP), 7687 (Bolt) |

## 验证步骤

### 1. 启动容器

```bash
docker run -d --name graphvi-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password123 \
  -e NEO4J_PLUGINS='["apoc"]' \
  graphvi-neo4j-apoc:5
```

### 2. 创建向量索引

```cypher
CREATE VECTOR INDEX test_vector IF NOT EXISTS
FOR (n:TestNode) ON (n.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 4,
  `vector.similarity_function`: 'cosine'
}};
```

> **注意**：参数名是 `vector.similarity_function`，不是 `vector.similarity`。

### 3. 插入示例数据

```cypher
CREATE (e1:TestNode:Event {
  title: '巴威台风应急保障',
  desc: '浙江省应急事件',
  embedding: [0.1, 0.2, 0.3, 0.4]
})
CREATE (e2:TestNode:Event {
  title: '会议保障任务',
  desc: '重要会议通信保障',
  embedding: [0.2, 0.1, 0.4, 0.3]
})
CREATE (e3:TestNode:Event {
  title: '地震救援行动',
  desc: '地震应急通信',
  embedding: [0.9, 0.8, 0.1, 0.2]
})
CREATE (p1:TestNode:PortableStation {
  name: '便携站-A',
  status: '使用中',
  embedding: [0.3, 0.4, 0.2, 0.1]
})
CREATE (p2:TestNode:PortableStation {
  name: '便携站-B',
  status: '空闲',
  embedding: [0.4, 0.3, 0.1, 0.2]
})
```

### 4. 向量相似度查询

```cypher
-- 计算相似度（不使用索引）
MATCH (n:TestNode)
WITH n, vector.similarity.cosine(n.embedding, [0.15, 0.15, 0.35, 0.35]) AS score
ORDER BY score DESC
RETURN n.title, n.name, score;
```

**结果**：

| title | name | score |
|-------|------|-------|
| 巴威台风应急保障 | NULL | 0.9916 |
| 会议保障任务 | NULL | 0.9916 |
| NULL | 便携站-B | 0.8559 |
| NULL | 便携站-A | 0.8559 |
| 地震救援行动 | NULL | 0.7729 |

### 5. 向量索引加速查询

```cypher
CALL db.index.vector.queryNodes('test_vector', 3, [0.1, 0.2, 0.3, 0.4])
YIELD node, score
RETURN labels(node), node.title, node.name, score;
```

**结果**：

| labels(node) | title | name | score |
|-------------|-------|------|-------|
| ["TestNode","Event"] | 巴威台风应急保障 | NULL | 0.9999 |
| ["TestNode","Event"] | 会议保障任务 | NULL | 0.9664 |
| ["TestNode","PortableStation"] | NULL | 便携站-B | 0.8492 |

## 结论

Neo4j 5.26.26 完整支持向量索引：

| 功能 | 支持情况 |
|------|---------|
| 创建向量索引 (`CREATE VECTOR INDEX`) | ✅ |
| 余弦相似度计算 (`vector.similarity.cosine`) | ✅ |
| 向量索引加速查询 (`db.index.vector.queryNodes`) | ✅ |
| 可配置维度数、索引参数 | ✅ |
| APOC 插件 | ✅ |

## 与 `neo4j-graphrag` 的集成

当前系统已安装 `neo4j-graphrag` 库，可直接使用 `VectorRetriever`：

```python
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.embeddings import OpenAIEmbeddings

retriever = VectorRetriever(
    driver=driver,
    index_name="event_vector_index",
    embedder=OpenAIEmbeddings(model="text-embedding-3-small"),
)
results = retriever.search("应急保障事件", top_k=5)
```

需要确定 embedding 模型后再集成到应用中。
