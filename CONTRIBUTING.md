# Contributing to Demo Forge

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/video_generator.git`
3. **Create a branch**: `git checkout -b feature/your-feature-name`

## Development Setup

### Backend (Pipeline)

```bash
pip install -r requirements.txt
cd project/videogen
python cli.py --help
```

### Frontend

```bash
cd project/videogen/frontend
npm install
npm run dev
```

### Environment Variables

```bash
export GOOGLE_API_KEY="..."        # Required - Gemini + Veo + Imagen
export ELEVENLABS_API_KEY="..."    # Optional - TTS, cloning, music
```

## Making Changes

1. Keep changes focused - one feature or fix per PR
2. Follow existing code style and conventions
3. Test your changes locally before submitting
4. Update documentation if you change behavior

## Pull Request Process

1. Update the README.md if your changes affect usage
2. Write a clear PR title and description
3. Reference any related issues (e.g., "Fixes #123")
4. Ensure the frontend builds without errors: `npm run build`
5. Wait for review from a maintainer

## Commit Messages

Use clear, descriptive commit messages:

- `fix: resolve audio ducking threshold issue`
- `feat: add support for PDF input files`
- `docs: update API endpoint documentation`

## Project Structure

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

## Reporting Issues

- Use GitHub Issues to report bugs or request features
- Include steps to reproduce for bug reports
- Include your environment details (OS, Node version, Python version)

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
