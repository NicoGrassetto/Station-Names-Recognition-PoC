# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release of GPT Realtime Starter Kit.
- FastAPI backend with OpenAI Agents SDK (`RealtimeAgent`, `RealtimeRunner`).
- React/TypeScript frontend with WebSocket-based real-time communication.
- Multiple interaction modes: voice assistant, push-to-talk, transcription,
  text chat, text-to-speech, and vision.
- Built-in tools: `get_weather`, `search_knowledge_base`.
- Prompty-based prompt management with hot-reloadable `.prompty` files.
- Azure infrastructure (Bicep) for Azure OpenAI with RBAC.
- Azure Developer CLI (`azd`) support for one-command provisioning.
