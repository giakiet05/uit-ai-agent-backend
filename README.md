# UIT AI Assistant

UIT AI Assistant is an AI-powered academic assistant for students at the University of Information Technology. The system combines a stateful LangGraph agent, Retrieval-Augmented Generation (RAG), a Model Context Protocol (MCP) tool server, and a Go API Gateway into a modular backend-oriented architecture.

The project is designed around two core goals:

- Answer academic questions using university regulations and curriculum documents as grounded context.
- Provide a scalable service architecture where AI orchestration, retrieval tools, API routing, persistence, and frontend clients are separated cleanly.

## System Overview

The system is organized as a multi-service application:

```text
Client
  |
  | HTTP/REST
  v
Go API Gateway
  |
  | gRPC
  v
Python LangGraph Agent
  |
  | MCP over streamable HTTP
  v
Python MCP Server
  |
  | LlamaIndex + ChromaDB + reranking
  v
Knowledge Base
```

Main services:

- `api-gateway`: Go service responsible for authentication, REST APIs, chat sessions, message persistence, Redis integration, and gRPC communication with the agent.
- `agent`: Python service that runs a stateful LangGraph ReAct-style agent with LangChain tool calling and checkpointer-backed multi-turn context.
- `mcp-server`: Python FastMCP service implementing a Model Context Protocol server for retrieval tools.
- `knowledge-builder`: Offline Python pipeline for parsing, cleaning, chunking, metadata generation, and vector indexing of academic documents.
- `web`: React frontend for interacting with the assistant.
- `browser-extension`: Browser extension integration.
- `modal-services`: Serverless reranking service for Vietnamese retrieval relevance.

## Repository Structure

```text
.
|-- apps
|   |-- agent                 # LangGraph agent service exposed through gRPC
|   |-- api-gateway           # Go API Gateway, auth, chat APIs, persistence
|   |-- browser-extension     # Browser extension integration
|   |-- knowledge-builder     # Offline document processing and indexing pipeline
|   |-- mcp-server            # FastMCP server exposing AI tools over MCP
|   `-- web                   # React web client
|-- packages
|   |-- proto                 # Shared gRPC protobuf definitions
|   `-- modal-services        # Modal GPU reranking service
|-- infra                     # Docker Compose infrastructure definitions
|-- docs                      # Technical reports, diagrams, and CV source
|-- data                      # Local data workspace for processed documents
|-- backup                    # Archived datasets and vector store snapshots
`-- experiments               # Retrieval and document parsing experiments
```

## Core Architecture

### Go API Gateway

The API Gateway is implemented in Go using Gin. It handles the application-facing backend responsibilities:

- User authentication and protected API routes.
- Chat session and message management.
- MongoDB persistence for user-facing chat history.
- Redis-backed runtime state and cache.
- gRPC communication with the Python agent service.
- WebSocket infrastructure for event delivery.

The gateway deliberately does not own AI reasoning logic. It delegates AI execution to the agent service through gRPC and focuses on request routing, validation, persistence, and service integration.

### LangGraph Agent Service

The agent service is implemented in Python with LangGraph and LangChain. It uses a ReAct-style graph:

```text
START -> agent node -> tools node -> agent node -> END
```

The `agent` node calls the LLM with available tools bound through LangChain. When the LLM requests tool usage, the `tools` node executes those tools and returns observations back into the graph. The loop continues until the model produces a final answer.

Key details:

- Stateful multi-turn conversations through LangGraph checkpointing.
- Thread IDs are derived from user/session context so the gateway does not need to resend full chat history.
- Tool calls are executed with timeout handling and parallel execution when multiple independent calls are requested.
- LLM provider abstraction supports OpenAI and Google Gemini models.

### Model Context Protocol Server

The MCP server is implemented with FastMCP. It exposes retrieval tools through the Model Context Protocol using streamable HTTP transport.

The LangGraph agent connects to this MCP server through `langchain-mcp-adapters`, enabling dynamic tool discovery and invocation instead of hard-coding retrieval logic inside the agent.

Current MCP retrieval tools include:

- `retrieve_regulation`: retrieves relevant university regulation chunks.
- `retrieve_curriculum`: retrieves relevant curriculum chunks.

This separation keeps the agent focused on reasoning while the MCP server owns tool schemas, retrieval execution, structured output, and retrieval-specific dependencies.

### Retrieval-Augmented Generation Pipeline

The RAG system is built with LlamaIndex and ChromaDB.

The offline indexing flow is handled by `apps/knowledge-builder`:

```text
Raw documents
  -> parsing
  -> cleaning
  -> metadata generation
  -> Vietnamese-aware chunking
  -> OpenAI embeddings
  -> ChromaDB collections
```

Important retrieval design choices:

- Separate ChromaDB collections for document categories such as regulations and curricula.
- OpenAI embedding model for dense semantic retrieval.
- Smart chunking tailored for Vietnamese academic documents, including regulation structure such as chapters and articles.
- Metadata enrichment so retrieved chunks carry document title, category, hierarchy, effective date, program metadata, and other useful fields.
- Structured retrieval responses validated through Pydantic models.

### Reranking and Program Filtering

Semantic search results are reranked with ViRanker, a Vietnamese reranking model deployed on Modal GPU. The retrieval server sends candidate chunks to the reranker, receives relevance scores, and returns the highest-ranked results to the agent.

The retrieval layer also includes program-based filtering for curriculum queries. This reduces confusion between similarly named academic programs such as Computer Science, Computer Engineering, Information Technology, and Information Systems.

## Data and Persistence

The system uses multiple storage layers, each with a clear responsibility:

- MongoDB: chat sessions, chat messages, user-facing conversation history.
- Redis: runtime cache and short-lived integration data.
- PostgreSQL: LangGraph checkpointing for agent conversation state.
- ChromaDB: vector database for indexed academic knowledge.

This split allows the UI history and the agent reasoning state to evolve independently. MongoDB stores what the user sees, while the checkpointer stores what the agent needs for stateful reasoning.

## Notable Technical Highlights

- Hybrid Go/Python backend: Go handles API routing and persistence, while Python handles AI orchestration and retrieval.
- Stateful LangGraph agent: ReAct-style workflow with checkpointed multi-turn context.
- MCP-based tool architecture: retrieval capabilities are served through a dedicated Model Context Protocol server implemented with FastMCP.
- Dynamic tool integration: the agent loads MCP tools through `langchain-mcp-adapters` instead of directly importing retrieval code.
- Vietnamese-focused RAG: document parsing, chunking, reranking, and program filtering are designed around Vietnamese academic documents.
- Modular retrieval stack: LlamaIndex, ChromaDB, OpenAI embeddings, structured Pydantic responses, and Modal-hosted ViRanker reranking.
- Service boundary clarity: API Gateway, agent, MCP server, knowledge builder, and frontend are separate services with explicit communication protocols.

## Communication Protocols

- Frontend to API Gateway: HTTP/REST.
- API Gateway to Agent: gRPC.
- Agent to MCP Server: MCP over streamable HTTP.
- MCP Server to vector store: local ChromaDB client.
- Retrieval reranking: HTTP request to Modal-hosted ViRanker endpoint.

## Project Status

This repository is a research and engineering project focused on building a practical AI assistant architecture for Vietnamese academic information retrieval. The main engineering work is in the backend and AI layers: service decomposition, stateful agent orchestration, MCP tool integration, RAG indexing, retrieval quality, and persistence design.
