import os
from neo4j import AsyncGraphDatabase, AsyncDriver


class Neo4jConnectionManager:
    def __init__(self):
        self._connections: dict[str, AsyncDriver] = {}

    def _key(self, uri: str, username: str, password: str) -> str:
        return f"{uri}|{username}|{password}"

    async def get_connection(self, uri: str, username: str, password: str) -> AsyncDriver:
        key = self._key(uri, username, password)
        if key not in self._connections:
            driver = AsyncGraphDatabase.driver(
                uri,
                auth=(username, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=10,
            )
            self._connections[key] = driver
        return self._connections[key]

    async def run_query(
        self,
        cypher: str,
        uri: str,
        username: str,
        password: str,
        database: str,
        parameters: dict | None = None,
    ):
        driver = await self.get_connection(uri, username, password)
        async with driver.session(database=database) as session:
            result = await session.run(cypher, parameters or {})
            records = [record async for record in result]
            summary = await result.consume()
            return records, summary

    async def close_all(self):
        for driver in self._connections.values():
            await driver.close()
        self._connections.clear()


conn_manager = Neo4jConnectionManager()
