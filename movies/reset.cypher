// 清空所有数据、约束和索引
MATCH (n) DETACH DELETE n;

// 删除所有约束
SHOW CONSTRAINTS YIELD name, type
CALL db.dropConstraint(name) YIELD name
RETURN count(name) AS dropped_constraints;

// 删除所有索引（包括向量索引）
SHOW INDEXES YIELD name, type, entityType
CALL db.dropIndex(name) YIELD name
RETURN count(name) AS dropped_indexes;
