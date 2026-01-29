# Technology Stack - RCN Server

This document outlines the core technologies used in the RCN Ecosystem, split into `rcn-core` and `rcn-web`.

## 1. Core Languages & Runtimes
- **Python:** The primary programming language.

## 2. Frameworks & Servers
- **FastAPI:** Used for building the API and server-side logic.
- **Uvicorn:** The ASGI server implementation.
- **FastMCP:** Integration for MCP (Model Context Protocol) servers.

## 3. Project Structure
- **rcn-core:** Generic infrastructure library.
    - Dependencies: `aiohttp`, `aiofiles`, `fastapi`, `fastmcp`, `ruamel.yaml`, `xxhash`.
- **rcn-web:** Web reconnaissance application.
    - Dependencies: `rcn-core` (Editable), `mitmproxy`.

## 4. Communication & Integration
- **EWP (Emacs Web Proxy):** Integration with an internal web proxy for traffic inspection and modification.
- **Mitmproxy:** Used for deep HTTP/HTTPS traffic analysis.

## 5. Automation & Reconnaissance
- **Targeted Integration:** Designed to integrate with a wide range of security tools (e.g., Nuclei, FFUF).
- **Scheduled Tasks:** Custom async task runner for periodic scanning and data processing.

## 6. Quality Assurance & Testing
- **Pytest:** The primary testing framework for unit and integration tests.
- **AnyIO:** For testing asynchronous components.

## 7. Data Management & Utilities
- **Redis:** For caching or message brokering.
- **SQLite:** Used for structured data storage (`rcn_automation_data.db`).
- **JQ:** Minimal use for JSON processing.
- **Aiohttp / Aiofiles:** For asynchronous networking and file operations.