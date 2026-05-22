from neo4j import AsyncGraphDatabase, AsyncDriver

from backend.settings_db import get_all_settings


class Neo4jConnectionManager:
    def __init__(self):
        self._driver: AsyncDriver | None = None

    def _read_config(self) -> tuple:
        s = get_all_settings()
        return (
            s.get("neo4j_uri", "bolt://localhost:7687"),
            s.get("neo4j_username", "neo4j"),
            s.get("neo4j_password", ""),
            s.get("neo4j_database", "neo4j"),
        )

    async def get_connection(self) -> AsyncDriver:
        if self._driver is None:
            uri, user, pwd, _ = self._read_config()
            self._driver = AsyncGraphDatabase.driver(
                uri,
                auth=(user, pwd),
                max_connection_lifetime=3600,
                max_connection_pool_size=10,
            )
        return self._driver

    async def reconnect(self):
        if self._driver:
            await self._driver.close()
            self._driver = None
        uri, user, pwd, _ = self._read_config()
        self._driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, pwd),
            max_connection_lifetime=3600,
            max_connection_pool_size=10,
        )

    async def run_query(
        self,
        cypher: str,
        parameters: dict | None = None,
    ):
        driver = await self.get_connection()
        _, _, _, database = self._read_config()
        async with driver.session(database=database) as session:
            result = await session.run(cypher, parameters or {})
            records = [record async for record in result]
            summary = await result.consume()
            return records, summary

    async def close_all(self):
        if self._driver:
            await self._driver.close()
            self._driver = None


conn_manager = Neo4jConnectionManager()
