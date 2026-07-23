// 1. 创建唯一约束
CREATE CONSTRAINT movie_id IF NOT EXISTS FOR (m:Movie) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT language_name IF NOT EXISTS FOR (l:Language) REQUIRE l.name IS UNIQUE;
CREATE CONSTRAINT district_name IF NOT EXISTS FOR (d:District) REQUIRE d.name IS UNIQUE;

// 2. 导入电影节点
LOAD CSV WITH HEADERS FROM 'file:///movies.csv' AS row
CREATE (m:Movie {
  id: toInteger(row.id),
  title: row.title,
  url: row.url,
  cover: row.cover,
  rate: toFloat(row.rate),
  showtime: toInteger(row.showtime),
  length: toInteger(row.length),
  othername: row.othername
});

// 3. 导入人物节点
LOAD CSV WITH HEADERS FROM 'file:///persons.csv' AS row
MERGE (p:Person {name: row.name});

// 4. 导入分类节点
LOAD CSV WITH HEADERS FROM 'file:///categories.csv' AS row
MERGE (c:Category {name: row.name});

// 5. 导入语言节点
LOAD CSV WITH HEADERS FROM 'file:///languages.csv' AS row
MERGE (l:Language {name: row.name});

// 6. 导入地区节点
LOAD CSV WITH HEADERS FROM 'file:///districts.csv' AS row
MERGE (d:District {name: row.name});

// 7. 导入 ACTED_IN 关系
LOAD CSV WITH HEADERS FROM 'file:///ACTED_IN.csv' AS row
MATCH (p:Person {name: row.actor})
MATCH (m:Movie {id: toInteger(row.movie_id)})
CREATE (p)-[:ACTED_IN]->(m);

// 8. 导入 DIRECTED 关系
LOAD CSV WITH HEADERS FROM 'file:///DIRECTED.csv' AS row
MATCH (p:Person {name: row.director})
MATCH (m:Movie {id: toInteger(row.movie_id)})
CREATE (p)-[:DIRECTED]->(m);

// 9. 导入 COMPOSED 关系
LOAD CSV WITH HEADERS FROM 'file:///COMPOSED.csv' AS row
MATCH (p:Person {name: row.composer})
MATCH (m:Movie {id: toInteger(row.movie_id)})
CREATE (p)-[:COMPOSED]->(m);

// 10. 导入 CATEGORIZED_TO 关系
LOAD CSV WITH HEADERS FROM 'file:///CATEGORIZED_TO.csv' AS row
MATCH (m:Movie {id: toInteger(row.movie_id)})
MATCH (c:Category {name: row.category})
CREATE (m)-[:CATEGORIZED_TO]->(c);

// 11. 导入 RELEASED_IN 关系
LOAD CSV WITH HEADERS FROM 'file:///RELEASED_IN.csv' AS row
MATCH (m:Movie {id: toInteger(row.movie_id)})
MATCH (d:District {name: row.region})
CREATE (m)-[:RELEASED_IN]->(d);

// 12. 导入 HAS_MAIN_LANGUAGE 关系
LOAD CSV WITH HEADERS FROM 'file:///HAS_MAIN_LANGUAGE.csv' AS row
MATCH (m:Movie {id: toInteger(row.movie_id)})
MATCH (l:Language {name: row.language})
CREATE (m)-[:HAS_MAIN_LANGUAGE]->(l);
