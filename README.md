# Vibe2Crazy - Remote Code Editing Tool

your development environment from anywhere. Generate code and run terminals remotely through your browser.
| Terminal | Files |
|-----|-----|
|<img width="320" height="704" alt="20260503233504_321_50" src="https://github.com/user-attachments/assets/4d6514a7-0482-49c5-b804-64f90c60da04" />|<img width="320" height="704" alt="20260503233506_323_50" src="https://github.com/user-attachments/assets/d2f6e1e2-cc68-4269-9df4-6eb712a5c71e" />|

Edit files on desktop:
<img width="2549" height="1352" alt="ScreenShot_2026-05-04_093318_605" src="https://github.com/user-attachments/assets/cf5f0403-b6a2-4c58-b989-f03851a49d60" />

Terminal matrix on desktop:
<img width="2549" height="1352" alt="ScreenShot_2026-05-04_092223_067" src="https://github.com/user-attachments/assets/9e57c821-5895-46a6-87dd-e0510988e354" />

## Key Features

- **Remote Access** - Connect to your code projects on remote servers via browser
- **Remote Terminal** - Run any agents cli in remote terminal(claude code / codex / opencode, etc..)
- **Code Editor** - Editor with syntax highlighting and diff viewer
- **Git Management** - One-click task branches, one-click merge to main

## Quick Start

### Install Guide

- sudo apt-get install git tmux ripgrep openssl universal-ctags
- Download binary file(vibe2crazy) in this project's release dir. Only support ubuntu x64 now.
- chmod +x vibe2crazy
- ./vibe2crazy
- then visit the web page at `localhost:8863`. Change default password when first acess.

### Remote Access

1. After logging in, click "Get token" to obtain the authorization token for remote connection. Currently, it is completely free and will remain so for a long time.
2. If you think this software is helpful, please consider subscribing to the annual plan to help us purchase more servers and improve the access experience.

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

## Designed for code review
- **Preview1/2** - Click the middle button of the mouse on the file to open the auxiliary preview view on the right.
- **Symbol** - The symbol view below the editor is used for quickly viewing the function definitions (Click 'Index' button first).

## Use Cases

- **Remote Work** - Access office dev environment from home or during travel
- **Multi-Device** - Access same dev environment from PC, tablet, or phone
- **Parallel Development** - Multiple tasks run simultaneously without interference
