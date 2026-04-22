"""
Dependency injection container.
Initializes all storage clients and the orchestrator on startup.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.orchestrator.llm_client import LLMClient
from backend.orchestrator.query_agent import QueryAgent
from backend.storage.graph_store import GraphStore
from backend.storage.search_store import SearchStore
from backend.storage.timeseries_store import TimeSeriesStore
from backend.storage.vector_store import VectorStore

security = HTTPBearer(auto_error=False)


class AppContainer:
    def __init__(self):
        self.vector: VectorStore = None
        self.graph: GraphStore = None
        self.ts: TimeSeriesStore = None
        self.search: SearchStore = None
        self.llm: LLMClient = None
        self.agent: QueryAgent = None

    async def init(self):
        self.vector = VectorStore()
        self.graph = GraphStore()

        self.ts = TimeSeriesStore()
        await self.ts.init_pool()

        self.search = SearchStore()
        await self.search.init_index()

        self.llm = LLMClient()

        self.agent = QueryAgent(
            vector=self.vector,
            graph=self.graph,
            ts=self.ts,
            search=self.search,
            llm=self.llm,
        )

    async def close(self):
        if self.ts:
            await self.ts.close()
        if self.search:
            await self.search.close()
        if self.graph:
            self.graph.close()


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_agent(container: AppContainer = Depends(get_container)) -> QueryAgent:
    return container.agent


def get_ts(container: AppContainer = Depends(get_container)) -> TimeSeriesStore:
    return container.ts


def get_vector(container: AppContainer = Depends(get_container)) -> VectorStore:
    return container.vector


async def get_current_officer(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Validate JWT from Keycloak.
    In dev mode (no Keycloak configured), returns a dummy officer.
    """
    from backend.config import settings
    if not settings.KEYCLOAK_CLIENT_SECRET:
        # Dev mode — no auth
        return {"officer_id": "dev_officer", "name": "Dev Officer", "role": "admin"}

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        from keycloak import KeycloakOpenID
        keycloak = KeycloakOpenID(
            server_url=settings.KEYCLOAK_URL,
            realm_name=settings.KEYCLOAK_REALM,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
        )
        token_info = keycloak.introspect(credentials.credentials)
        if not token_info.get("active"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        return {
            "officer_id": token_info.get("sub"),
            "name": token_info.get("name"),
            "role": token_info.get("realm_access", {}).get("roles", ["officer"])[0],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
