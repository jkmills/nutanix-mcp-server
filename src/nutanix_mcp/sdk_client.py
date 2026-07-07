"""Nutanix v4 SDK client wrapper.

Provides async-safe access to official Nutanix Python SDK clients.
SDK calls are synchronous, so we run them via asyncio.to_thread().
"""

import asyncio
from functools import cached_property
from typing import Any, Optional

from ntnx_clustermgmt_py_client import ApiClient as ClustermgmtApiClient
from ntnx_clustermgmt_py_client import Configuration as ClustermgmtConfiguration
from ntnx_clustermgmt_py_client.api import ClustersApi, StorageContainersApi
from ntnx_dataprotection_py_client import ApiClient as DataprotectionApiClient
from ntnx_dataprotection_py_client import Configuration as DataprotectionConfiguration
from ntnx_dataprotection_py_client.api import RecoveryPointsApi
from ntnx_networking_py_client import ApiClient as NetworkingApiClient
from ntnx_networking_py_client import Configuration as NetworkingConfiguration
from ntnx_networking_py_client.api import SubnetsApi
from ntnx_prism_py_client import ApiClient as PrismApiClient
from ntnx_prism_py_client import Configuration as PrismConfiguration
from ntnx_prism_py_client.api import CategoriesApi
from ntnx_prism_py_client.api import TasksApi as PrismTasksApi
from ntnx_vmm_py_client import ApiClient as VmmApiClient
from ntnx_vmm_py_client import Configuration as VmmConfiguration
from ntnx_vmm_py_client.api import ImagesApi, VmApi

from nutanix_mcp.config import Settings


def _model_to_dict(obj: Any) -> Any:
    """Convert SDK model objects to plain dicts recursively."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_model_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _model_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return obj


class NutanixSDKClient:
    """Async wrapper around official Nutanix v4 Python SDKs.

    Each namespace gets its own Configuration + ApiClient, lazily created.
    All SDK calls are synchronous internally, so we use asyncio.to_thread()
    to avoid blocking the event loop.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._vmm_client: Optional[VmmApiClient] = None
        self._clustermgmt_client: Optional[ClustermgmtApiClient] = None
        self._networking_client: Optional[NetworkingApiClient] = None
        self._prism_client: Optional[PrismApiClient] = None
        self._dataprotection_client: Optional[DataprotectionApiClient] = None

    def _make_config(self, config_class: type) -> Any:
        """Create a configuration instance for any namespace SDK."""
        config = config_class()
        config.host = self.settings.host
        config.port = str(self.settings.port)
        config.username = self.settings.username
        config.password = self.settings.password.get_secret_value() if self.settings.password else None
        config.verify_ssl = self.settings.verify_ssl
        config.max_retry_attempts = 3
        config.backoff_factor = 2
        config.read_timeout = self.settings.timeout * 1000  # SDK uses milliseconds
        config.connect_timeout = self.settings.timeout * 1000
        return config

    # ─── VMM namespace ────────────────────────────────────────────────────

    @cached_property
    def _vmm_api_client(self) -> VmmApiClient:
        config = self._make_config(VmmConfiguration)
        return VmmApiClient(configuration=config)

    @cached_property
    def vm_api(self) -> VmApi:
        return VmApi(api_client=self._vmm_api_client)

    @cached_property
    def image_api(self) -> ImagesApi:
        return ImagesApi(api_client=self._vmm_api_client)

    # ─── Clustermgmt namespace ────────────────────────────────────────────

    @cached_property
    def _clustermgmt_api_client(self) -> ClustermgmtApiClient:
        config = self._make_config(ClustermgmtConfiguration)
        return ClustermgmtApiClient(configuration=config)

    @cached_property
    def cluster_api(self) -> ClustersApi:
        return ClustersApi(api_client=self._clustermgmt_api_client)

    @cached_property
    def storage_container_api(self) -> StorageContainersApi:
        return StorageContainersApi(api_client=self._clustermgmt_api_client)

    # ─── Networking namespace ─────────────────────────────────────────────

    @cached_property
    def _networking_api_client(self) -> NetworkingApiClient:
        config = self._make_config(NetworkingConfiguration)
        return NetworkingApiClient(configuration=config)

    @cached_property
    def subnet_api(self) -> SubnetsApi:
        return SubnetsApi(api_client=self._networking_api_client)

    # ─── Prism namespace ──────────────────────────────────────────────────

    @cached_property
    def _prism_api_client(self) -> PrismApiClient:
        config = self._make_config(PrismConfiguration)
        return PrismApiClient(configuration=config)

    @cached_property
    def category_api(self) -> CategoriesApi:
        return CategoriesApi(api_client=self._prism_api_client)

    @cached_property
    def task_api(self) -> PrismTasksApi:
        return PrismTasksApi(api_client=self._prism_api_client)

    # ─── Data Protection namespace ────────────────────────────────────────

    @cached_property
    def _dataprotection_api_client(self) -> DataprotectionApiClient:
        config = self._make_config(DataprotectionConfiguration)
        return DataprotectionApiClient(configuration=config)

    @cached_property
    def recovery_point_api(self) -> RecoveryPointsApi:
        return RecoveryPointsApi(api_client=self._dataprotection_api_client)

    # ─── Async helpers ────────────────────────────────────────────────────

    @staticmethod
    def get_etag(api_response: Any) -> Optional[str]:
        """Extract the ETag from a GET response for If-Match concurrency control.

        Nutanix v4 APIs require the If-Match header on mutating operations
        (PUT, DELETE, and POST $actions); without it the API rejects the
        request with HTTP 428 Precondition Required.
        """
        return VmmApiClient.get_etag(api_response)

    async def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous SDK method in a thread to avoid blocking.

        Usage:
            result = await sdk.call(sdk.vm_api.list_vms, _filter="name eq 'test'")
        """
        return await asyncio.to_thread(func, *args, **kwargs)

    # Auto-pagination safety valve: 200 pages × 100 items = 20k entities max.
    # Prevents unbounded loops if a server keeps returning full pages.
    MAX_PAGES = 200

    async def list_all(self, list_func: Any, *args: Any, **kwargs: Any) -> list[Any]:
        """Auto-paginate a list endpoint that supports _page/_limit.

        Fetches all pages and returns combined data list.
        SDK pagination uses 0-based page index.

        Usage:
            vms = await sdk.list_all(sdk.vm_api.list_vms, _filter="powerState eq 'ON'")
            hosts = await sdk.list_all(sdk.cluster_api.list_hosts_by_cluster_id, cluster_id)
        """
        page = 0
        page_size = 100
        all_data: list[Any] = []

        while page < self.MAX_PAGES:
            response = await asyncio.to_thread(
                list_func, *args, _page=page, _limit=page_size, **kwargs
            )

            data = response.data if response.data else []
            all_data.extend(data)

            # Check if we've fetched everything
            total = None
            if hasattr(response, "metadata") and response.metadata:
                total = getattr(response.metadata, "total_available_results", None)

            if not data or len(data) < page_size:
                break
            if total is not None and len(all_data) >= total:
                break

            page += 1

        return all_data

    async def close(self) -> None:
        """No persistent connections to close for SDK clients."""
        pass
