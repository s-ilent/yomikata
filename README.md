# Yomikata

Yomikata is a desktop application designed to be a Japanese reading assistant. It helps users process and understand Japanese text by providing morphological analysis, multi-dictionary lookup, and AI-powered grammar explanations.

## Features

- **Text Analysis**: Morphological analysis (via Fugashi/MeCab) to break down Japanese text into tokens, with readings for kanji, kana, and romaji.
- **Dictionary Lookup**: Efficient searching across your personal dictionary and secondary reference dictionaries.
- **AI Overview**: Context-aware grammar explanations and word definitions powered by LLMs (OpenAI-compatible APIs).
- **Personal Dictionary**: Save and manage your own vocabulary notes with support for Markdown definitions.
- **Customizable UI**: A clean, dark mode UI built with PyQt6.

## Architecture & Tech Stack

- **Language**: Python 3.13+
- **UI Framework**: PyQt6
- **Database**: SQLite with FTS5 and zstd compression
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Morphology**: Fugashi / MeCab

## Getting Started

### Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed on your system.

### Installation

1. Clone the repository.

2. Sync dependencies:
   ```bash
   uv sync
   ```

### Running the App

```bash
uv run src/main.py
```

## Development

We use `ruff` for linting and `mypy` for static type checking.

```bash
# Run linting
uv run ruff check .

# Run type checks
uv run mypy src/

# Run tests
uv run pytest tests/
```

## License

MIT License

Disclaimer: 99% of this code is written by AI, or is an existing library. No promises about the code quality!
