# Vibe2Crazy - Remote Code Editing Tool

Access your development environment from anywhere. Edit code and run terminals remotely through your browser.

## Key Features

- **Remote Access** - Connect to your code projects on remote servers via browser
- **Remote Terminal** - Full Linux terminal in web page with persistent tmux sessions
- **Code Editor** - VS Code's Monaco editor with syntax highlighting and diff viewer
- **Git Management** - One-click task branches, one-click merge to main

## Quick Start

### Login

Visit the website and enter your password.

### Create Project

1. Click "New Project"
2. Enter project name
3. Select or enter a Git repository path (auto-create Git repo supported)
4. Save project

### Create Task

Each task creates an independent Git branch and working directory.

1. Enter project, click "New Task"
2. Enter task name
3. Terminal opens automatically after task creation

### Use Terminal

- Terminal connects to task's isolated working directory
- Full Linux commands supported
- Session persists across page refreshes
- Switch tasks anytime, terminal keeps running in background

### Code Review & Merge

1. Click "Code Review" to enter editor
2. View changed files and code differences
3. Click "Merge" button when ready
4. Code merges to main branch automatically, task completed

## Use Cases

- **Remote Work** - Access office dev environment from home or during travel
- **Multi-Device** - Access same dev environment from PC, tablet, or phone
- **Parallel Development** - Multiple tasks run simultaneously without interference
- **Claude Code** - Use Claude Code CLI for AI-assisted programming in remote environment

## Access URL

Development: `http://your-server:5173`
Production: `http://your-server:8864`

## Support

Contact your administrator for assistance.