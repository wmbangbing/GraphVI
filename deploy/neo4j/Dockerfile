FROM neo4j:5

COPY deploy/neo4j/apoc.jar /plugins/apoc.jar

ENV NEO4J_PLUGINS='["apoc"]'
ENV NEO4J_dbms_security_procedures_unrestricted=apoc.*
