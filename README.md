# Vibe2Crazy - Remote Code Editing Tool

Access your development environment from anywhere. Generate code and run terminals remotely through your browser.
<img width="480" height="1056" alt="20260503233504_321_50" src="https://github.com/user-attachments/assets/4d6514a7-0482-49c5-b804-64f90c60da04" />
<br>
<img width="480" height="1056" alt="20260503233506_323_50" src="https://github.com/user-attachments/assets/d2f6e1e2-cc68-4269-9df4-6eb712a5c71e" />


## Key Features

- **Remote Access** - Connect to your code projects on remote servers via browser
- **Remote Terminal** - Run any agents cli in remote terminal(claude code / codex / opencode, etc..)
- **Code Editor** - Editor with syntax highlighting and diff viewer
- **Git Management** - One-click task branches, one-click merge to main

## Quick Start

### Install Guide

- Download binary file(vibe2crazy) in this project's release dir. Only support ubuntu x64.
- chmod +x vibe2crazy
- ./vibe2crazy
- then visit the web page at `localhost:8863`. Change default password when first acess.

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
