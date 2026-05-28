# neo4j-graphrag 源码分析

基于 `neo4j-graphrag==1.14.1` 源码分析。

## 组件架构

```
Text2CypherRetriever
  ├── 依赖: Retriever (base), LLMInterface, PromptTemplate
  ├── 构造函数: 接收 driver, llm, neo4j_schema, examples, custom_prompt
  └── 核心调用链:
      search(query_text)
        → get_search_results(query_text)
           → Text2CypherTemplate.format(schema, examples, query_text)  ← ①
           → llm.invoke(prompt)                                        ← ②
           → extract_cypher(text)                                      ← ③
           → driver.execute_query(cypher)                              ← ④
```

## 四个关键阶段

### ① Prompt 组装

文件: `generation/prompts.py` `Text2CypherTemplate.format()`

```python
prompt = prompt_template.format(
    schema=schema_to_use,
    examples=examples_to_use,
    query_text=validated_data.query_text,
)
```

最终调用 `self.template.format(**kwargs)`，即 Python 内置的 `str.format()`。

**这是整个库最脆弱的一环**：prompt 模板里任何未转义的 `{xxx}` 都会导致 `KeyError`。框架不做任何转义处理。

**正向**：灵活性高，用户可以自定义任意 prompt 格式。

**逆向**：prompt 中包含示例代码（如 `{prop: 'value'}`）时必须手动转义为 `{{prop: 'value'}}`。

### ② LLM 调用

文件: `llm/openai_llm.py` `OpenAILLM`

```python
class OpenAILLM(BaseOpenAILLM):
    def __init__(self, model_name, model_params=None, **kwargs):
        # **kwargs 透传给 openai.OpenAI()
        self.client = self.openai.OpenAI(**kwargs)
        self.async_client = self.openai.AsyncOpenAI(**kwargs)
```

关键行为：

- 构造时校验 `openai` 包是否安装，否则立即抛 `ImportError`
- `**kwargs` 直接传递给 OpenAI SDK，因此支持 `api_key`、`base_url` 等参数
- 支持同步 (`invoke`) 和异步 (`ainvoke`) 两种调用
- 自带速率限制处理 (`@rate_limit_handler_decorator`)，指数退避重试
- V1 接口（字符串 input）和 V2 接口（message list）自动分发

### ③ Cypher 提取

文件: `retrievers/text2cypher.py` `extract_cypher()`

```python
def extract_cypher(text: str) -> str:
    # 1) 从 ```cypher``` 代码块中提取
    # 2) 用正则给含空格的 label/property 加反引号
    # 3) 返回清洗后的 Cypher 语句
```

三步处理：

1. 正则提取 triple backticks 内的内容
2. 自动识别含空格的 node label / property key / relationship type 并加反引号
3. 返回纯 Cypher 字符串

### ④ 查询执行

文件: `retrievers/text2cypher.py` `get_search_results()`

```python
records, _, _ = self.driver.execute_query(
    t2c_query,
    database_=self.neo4j_database,
    routing_=neo4j.RoutingControl.READ,
)
```

- 固定使用 `RoutingControl.READ`，只读操作
- 执行结果以 `neo4j.Record` 列表返回
- 元数据中包含生成的 cypher 语句

## Schema 处理策略

`Text2CypherRetriever.__init__()` 中 schema 来源有四种情况：

| custom_prompt | neo4j_schema | 行为 |
|---|---|---|
| 提供 | 提供 | 使用传入的 schema（我们的使用方式） |
| 提供 | 不提供 | schema 为空字符串，prompt 中不包含 schema |
| 不提供 | 提供 | 使用传入的 schema，搭配框架默认 prompt |
| 不提供 | 不提供 | 自动调用库内 `get_schema()` 从 Neo4j 获取 |

框架自带的 `get_schema()`（`neo4j_graphrag.schema` 模块）与我们手写的 `_get_schema()` 功能基本一致：都使用 `db.schema.nodeTypeProperties()` 和 `db.schema.visualization()` 系统过程。

## Retriever 基类

文件: `retrievers/base.py`

```python
class Retriever(ABC):
    def __init__(self, driver, neo4j_database=None):
        # 启动时校验 Neo4j 版本兼容性
        # 检查是否支持 vector index 和 metadata filtering

    def search(self, *args, **kwargs) -> RetrieverResult:
        raw_result = self.get_search_results(*args, **kwargs)
        formatter = self.get_result_formatter()
        search_items = [formatter(record) for record in raw_result.records]
        return RetrieverResult(items=search_items, metadata=raw_result.metadata)
```

- 抽象类，子类必须实现 `get_search_results()`
- `search()` 是公共入口，内部调用 `get_search_results()` 后格式化结果
- 默认的 `result_formatter` 将 Record 转为 `str`（可覆写）
- 支持 `convert_to_tool()` 将其转为 LLM tool 调用格式

## 与我们系统的结合

```
nl2cypher.py
  ├─ _get_schema()       ← 手动构建 schema（含可选 sample 值）
  ├─ _get_llm()          ← 创建 OpenAILLM（透传 api_key, base_url）
  ├─ _get_examples()     ← 从预设问题取 few-shot 示例
  └─ nl2cypher()         ← 组装全部传给 Text2CypherRetriever
```

## 整体评价

这个库的本质是一个**轻量编排层**，核心职责就是三步：

1. **拼提示词** — 用 `str.format()` 拼接 prompt，无模板安全处理
2. **调 LLM** — 透传给 OpenAI SDK，带速率限制和重试
3. **执行 Cypher** — 用 Neo4j driver 执行生成的语句

**Text2Cypher 能力完全取决于 LLM**，框架本身不做：
- Cypher 语法校验
- 结果正确性验证
- Schema 理解或推理
- Prompt 安全检查

schema 和 examples 仅作为纯文本字符串塞入 prompt 中，所有"智能"都来自 LLM 自身。
