# Contributing to GPT Realtime Starter Kit

Thank you for your interest in contributing! This guide will help you get
started.

## Getting Started

1. **Fork** the repository and clone your fork locally.
2. **Install dependencies**:

   ```bash
   # Backend
   pip install -r requirements.txt

   # Frontend
   cd frontend && npm install
   ```

3. **Set up Azure resources** (if testing end-to-end):

   ```bash
   azd up
   ```

4. Create a new **branch** for your work:

   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Backend (Python / FastAPI)

- Entry point: `src/main.py`
- Agent factory: `src/agent.py`
- Tools: `tools/` — add new `@function_tool` functions here
- Prompts: `prompts/` — add or edit `.prompty` files
- Modes: `config/modes/` — add new YAML mode presets

### Frontend (React / TypeScript)

- Source: `frontend/src/`
- Run the dev server: `cd frontend && npm run dev`

## How to Contribute

### Reporting Bugs

- Open an [issue](../../issues) with a clear title and description.
- Include steps to reproduce, expected behavior, and actual behavior.
- Add relevant logs, screenshots, or error messages.

### Suggesting Features

- Open an [issue](../../issues) with the `enhancement` label.
- Describe the use case and why it would be valuable.

### Submitting Pull Requests

1. Ensure your code follows the existing style and conventions.
2. Keep pull requests focused — one feature or fix per PR.
3. Add or update tests if applicable.
4. Update documentation (README, inline comments) as needed.
5. Write a clear PR description explaining **what** and **why**.

## Code Style

- **Python**: Follow [PEP 8](https://pep8.org/). Use type hints where practical.
- **TypeScript/React**: Follow the existing ESLint/Prettier configuration.
- **YAML configs**: Use 2-space indentation and add comments for clarity.

## Commit Messages

Use clear, descriptive commit messages:

```
feat: add real-time transcription mode
fix: resolve WebSocket reconnection on timeout
docs: update deployment instructions
```

Follow [Conventional Commits](https://www.conventionalcommits.org/) when
possible.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code.

## Questions?

If you have questions about contributing, feel free to open a
[discussion](../../discussions) or reach out via an issue.

Thank you for helping improve the GPT Realtime Starter Kit!
