"""Nutanix Prism Central API client with v4/v3 version routing."""

from typing import Any, Optional

import httpx

from nutanix_mcp.config import Settings


class NutanixAPIError(Exception):
    """Base exception for Nutanix API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class AuthenticationError(NutanixAPIError):
    """Authentication failed."""
    pass


class NotFoundError(NutanixAPIError):
    """Resource not found."""
    pass


class ValidationError(NutanixAPIError):
    """Request validation failed."""
    pass


class NutanixClient:
    """Async HTTP client for Nutanix Prism Central.

    Prefers v4 API endpoints, falls back to v3/v2 when needed.
    v4 uses OData-style query params ($filter, $orderby, $top, $skip).
    v3 uses POST-based list with body filters.
    """

    V4_VERSION = "v4.0"
    V3_VERSION = "v3"
    V2_VERSION = "v2.0"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[httpx.AsyncClient] = None
        self._pe_clients: dict[str, httpx.AsyncClient] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url,
                headers={
                    **self.settings.get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                verify=self.settings.verify_ssl,
                timeout=httpx.Timeout(self.settings.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        for pe_client in self._pe_clients.values():
            if not pe_client.is_closed:
                await pe_client.aclose()
        self._pe_clients.clear()

    # ─── v4 API methods ───────────────────────────────────────────────────

    async def v4_get(
        self,
        namespace: str,
        path: str,
        params: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """GET request against v4 API.

        Args:
            namespace: API namespace (e.g., 'vmm', 'clustermgmt', 'prism')
            path: Resource path (e.g., 'ahv/config/vms')
            params: Optional OData query parameters
        """
        client = await self._get_client()
        url = f"/{namespace}/{self.V4_VERSION}/{path}"

        try:
            response = await client.get(url, params=params)
        except httpx.ConnectError as e:
            raise NutanixAPIError(
                f"Connection failed to {self.settings.host}:{self.settings.port}",
                details=str(e),
            )
        except httpx.TimeoutException as e:
            raise NutanixAPIError(
                f"Request timed out after {self.settings.timeout}s",
                details=str(e),
            )

        if response.status_code >= 400:
            self._handle_error(response)

        return response.json()

    async def v4_post(
        self,
        namespace: str,
        path: str,
        body: dict[str, Any],
        params: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """POST request against v4 API."""
        client = await self._get_client()
        url = f"/{namespace}/{self.V4_VERSION}/{path}"

        try:
            response = await client.post(url, json=body, params=params)
        except httpx.ConnectError as e:
            raise NutanixAPIError(
                f"Connection failed to {self.settings.host}:{self.settings.port}",
                details=str(e),
            )
        except httpx.TimeoutException as e:
            raise NutanixAPIError(
                f"Request timed out after {self.settings.timeout}s",
                details=str(e),
            )

        if response.status_code >= 400:
            self._handle_error(response)

        return response.json()

    async def v4_list(
        self,
        namespace: str,
        path: str,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        select: Optional[str] = None,
    ) -> dict[str, Any]:
        """List resources using v4 API with OData query parameters.

        Args:
            namespace: API namespace (e.g., 'vmm', 'clustermgmt')
            path: Resource path
            filter: OData $filter expression
            orderby: OData $orderby expression
            top: Maximum number of results
            skip: Number of results to skip
            select: Fields to include in response
        """
        params: dict[str, str] = {}
        if filter:
            params["$filter"] = filter
        if orderby:
            params["$orderby"] = orderby
        if top is not None:
            params["$top"] = str(top)
        if skip is not None:
            params["$skip"] = str(skip)
        if select:
            params["$select"] = select

        return await self.v4_get(namespace, path, params=params)

    # ─── v3 API methods (fallback) ────────────────────────────────────────

    async def v3_list(
        self,
        resource: str,
        kind: str,
        filter: Optional[str] = None,
        length: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List entities using v3 API (POST /api/nutanix/v3/{resource}/list).

        Used as fallback when v4 doesn't support a resource.
        """
        client = await self._get_client()
        url = f"/nutanix/{self.V3_VERSION}/{resource}/list"

        body: dict[str, Any] = {
            "kind": kind,
            "length": length,
            "offset": offset,
        }
        if filter:
            body["filter"] = filter

        try:
            response = await client.post(url, json=body)
        except httpx.ConnectError as e:
            raise NutanixAPIError(
                f"Connection failed to {self.settings.host}:{self.settings.port}",
                details=str(e),
            )
        except httpx.TimeoutException as e:
            raise NutanixAPIError(
                f"Request timed out after {self.settings.timeout}s",
                details=str(e),
            )

        if response.status_code >= 400:
            self._handle_error(response)

        return response.json()

    async def v3_get(
        self,
        resource: str,
        uuid: str,
    ) -> dict[str, Any]:
        """Get a single entity by UUID using v3 API."""
        client = await self._get_client()
        url = f"/nutanix/{self.V3_VERSION}/{resource}/{uuid}"

        try:
            response = await client.get(url)
        except httpx.ConnectError as e:
            raise NutanixAPIError(
                f"Connection failed to {self.settings.host}:{self.settings.port}",
                details=str(e),
            )
        except httpx.TimeoutException as e:
            raise NutanixAPIError(
                f"Request timed out after {self.settings.timeout}s",
                details=str(e),
            )

        if response.status_code >= 400:
            self._handle_error(response)

        return response.json()

    # ─── Prism Element v2 API methods ─────────────────────────────────────

    async def _get_pe_client(self, pe_host: str) -> httpx.AsyncClient:
        """Get or create an HTTP client for a Prism Element node."""
        if pe_host not in self._pe_clients or self._pe_clients[pe_host].is_closed:
            self._pe_clients[pe_host] = httpx.AsyncClient(
                base_url=f"https://{pe_host}:{self.settings.port}/api/nutanix/{self.V2_VERSION}",
                headers={
                    **self.settings.get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                verify=self.settings.verify_ssl,
                timeout=httpx.Timeout(self.settings.timeout),
            )
        return self._pe_clients[pe_host]

    async def pe_get(
        self,
        pe_host: str,
        path: str,
        params: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """GET request against a Prism Element v2 API.

        Args:
            pe_host: Prism Element CVM IP or hostname
            path: Resource path (e.g., 'vms', 'hosts', 'cluster')
        """
        client = await self._get_pe_client(pe_host)

        try:
            response = await client.get(f"/{path}", params=params)
        except httpx.ConnectError as e:
            raise NutanixAPIError(
                f"Connection failed to PE host {pe_host}",
                details=str(e),
            )
        except httpx.TimeoutException as e:
            raise NutanixAPIError(
                f"Request to PE {pe_host} timed out after {self.settings.timeout}s",
                details=str(e),
            )

        if response.status_code >= 400:
            self._handle_error(response)

        return response.json()

    async def pe_list(
        self,
        pe_host: str,
        resource: str,
        count: Optional[int] = None,
        filter_criteria: Optional[str] = None,
    ) -> dict[str, Any]:
        """List resources from a Prism Element node using v2 API.

        Args:
            pe_host: Prism Element CVM IP or hostname
            resource: Resource type (e.g., 'vms', 'hosts', 'disks', 'containers')
            count: Max results to return
            filter_criteria: Filter string for the query
        """
        params: dict[str, str] = {}
        if count is not None:
            params["count"] = str(count)
        if filter_criteria:
            params["filter_criteria"] = filter_criteria

        return await self.pe_get(pe_host, resource, params=params)

    # ─── Error handling ───────────────────────────────────────────────────

    def _handle_error(self, response: httpx.Response) -> None:
        """Raise appropriate exception based on HTTP status."""
        status = response.status_code
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
            details = error_data.get("details", None)
            if isinstance(details, list):
                details = "; ".join(str(d) for d in details)
        except Exception:
            message = response.text
            details = None

        if status in (401, 403):
            raise AuthenticationError(
                f"Authentication failed ({status}): {message}",
                status_code=status,
                details=details,
            )
        elif status == 404:
            raise NotFoundError(
                f"Not found: {message}",
                status_code=status,
                details=details,
            )
        elif status in (400, 422):
            raise ValidationError(
                f"Validation error: {message}",
                status_code=status,
                details=details,
            )
        else:
            raise NutanixAPIError(
                f"API error ({status}): {message}",
                status_code=status,
                details=details,
            )
