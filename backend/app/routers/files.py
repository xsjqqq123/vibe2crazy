from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, Form
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional
from app.database import get_db
from app.models import Task, Session
from app.schemas import FileNode, FileRead, FileWrite, FileDeleteResponse, ChangedFilesResponse, RevertResponse, FileUploadResponse, TempUploadResult, TempUploadResponse, PaginatedChangedFilesResponse
from app.auth import require_auth
from app.services.file_service import FileService, MAX_FILE_SIZE, format_file_size, MAX_UPLOAD_SIZE, TEMP_UPLOAD_DIR
from app.services.git_service import GitService
from pathlib import Path
import logging
import mimetypes
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["files"])


def check_file_size(worktree_path: str, file_path: str) -> tuple[bool, int, str]:
    """Check if file size is within limit.

    Returns: (is_within_limit, size_bytes, size_formatted)
    """
    try:
        full_path = Path(worktree_path) / file_path
        if full_path.exists() and full_path.is_file():
            size = full_path.stat().st_size
            return size <= MAX_FILE_SIZE, size, format_file_size(size)
        return True, 0, ""
    except Exception:
        return True, 0, ""


def get_media_type(file_path: str) -> str:
    """Get the media type (MIME type) for a file based on its extension."""
    # Initialize mimetypes if not already done
    mimetypes.init()

    # Get the media type from mimetypes
    media_type, _ = mimetypes.guess_type(file_path)

    print(f"[DEBUG] get_media_type: file_path={file_path}, guessed_type={media_type}")

    # Return the guessed type or default to octet-stream
    return media_type or "application/octet-stream"


@router.get("/{task_id}/files", response_model=List[FileNode])
async def list_files(
    task_id: str,
    path: Optional[str] = Query(None, description="Relative path to list (empty for top-level)"),
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """
    List files in task worktree (lazy loading)

    - Without `path` query parameter: returns top-level files and directories only
    - With `path` query parameter: returns immediate children of that directory only

    This enables lazy loading - the frontend can load directories on-demand
    instead of loading the entire file tree at once.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Build full directory path
    if path:
        # List specific subdirectory
        import os
        full_path = os.path.join(task.worktree_path, path)
        # Security check: ensure path is within worktree
        full_path_resolved = Path(full_path).resolve()
        worktree_resolved = Path(task.worktree_path).resolve()
        if not str(full_path_resolved).startswith(str(worktree_resolved)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path (outside worktree)"
            )
        tree = FileService.list_directory(str(full_path), path)
    else:
        # List top-level directory
        tree = FileService.list_directory(task.worktree_path, "")

    return tree


@router.get("/{task_id}/files/search")
async def search_files(
    task_id: str,
    query: str = Query("", description="Search query for filtering files (substring match)"),
    limit: int = Query(100, description="Maximum number of results to return"),
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """
    Search files in task worktree with server-side filtering.

    For optimal performance with large projects:
    - Server performs the filtering, reducing network payload
    - Results are limited to avoid overwhelming the client
    - Search uses simple substring matching on file paths

    Args:
        query: Search term to filter files (empty returns all files up to limit)
        limit: Maximum number of results (default: 100)

    Returns:
        Filtered and sorted list of file paths
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Use efficient search with filtering on the server side
    files = FileService.search_files(task.worktree_path, query.lower(), limit)

    return {"files": files}


# NOTE: /download route must come BEFORE /{file_path:path} because FastAPI matches routes in order
@router.get("/{task_id}/files/{file_path:path}/download")
async def download_file(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """
    Download a file or directory (as ZIP) from task worktree.

    - For files: Direct download with proper Content-Disposition
    - For directories: Download as ZIP archive

    Args:
        task_id: Task ID
        file_path: Path to file or directory (relative to worktree)

    Returns:
        FileResponse for download
    """
    import os
    from urllib.parse import unquote
    import io
    import zipfile

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # URL decode the file path
    file_path = unquote(file_path)
    full_path = Path(task.worktree_path) / file_path

    # Security check: ensure path is within worktree
    full_path_resolved = full_path.resolve()
    worktree_resolved = Path(task.worktree_path).resolve()
    if not str(full_path_resolved).startswith(str(worktree_resolved)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path (outside worktree)"
        )

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path not found: {file_path}"
        )

    # If it's a file, return directly
    if full_path.is_file():
        # Determine media type based on file extension
        media_type = "application/octet-stream"
        if file_path.endswith('.pdf'):
            media_type = "application/pdf"
        elif file_path.endswith('.txt') or file_path.endswith('.md'):
            media_type = "text/plain"
        elif file_path.endswith('.json'):
            media_type = "application/json"
        elif file_path.endswith('.xml'):
            media_type = "application/xml"
        elif file_path.endswith('.html') or file_path.endswith('.htm'):
            media_type = "text/html"
        elif file_path.endswith('.css'):
            media_type = "text/css"
        elif file_path.endswith('.js'):
            media_type = "text/javascript"
        elif file_path.endswith('.ts'):
            media_type = "text/typescript"
        elif file_path.endswith('.py'):
            media_type = "text/x-python"

        return FileResponse(
            str(full_path),
            media_type=media_type,
            filename=full_path.name
        )

    # If it's a directory, create ZIP and return
    if full_path.is_dir():
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        base_name = full_path.name or "download"

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(full_path):
                # Skip .git directory and its contents
                dirs[:] = [d for d in dirs if d != '.git']

                for file in files:
                    file_path_in_dir = os.path.join(root, file)
                    arcname = os.path.relpath(file_path_in_dir, full_path.parent)
                    zip_file.write(file_path_in_dir, arcname)

        zip_buffer.seek(0)

        # Return ZIP file
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{base_name}.zip"'
            }
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid path type: {file_path}"
    )


@router.get("/{task_id}/files/{file_path:path}/hash")
async def get_file_hash(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """
    Get SHA-256 hash of file content for cache validation.

    Returns a hash that clients can use to check if their cached
    version of a file is still valid.

    Returns:
        {"hash": "sha256:<hex_value>"}
    """
    import os
    from urllib.parse import unquote

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # URL decode the file path
    file_path = unquote(file_path)
    full_path = os.path.join(task.worktree_path, file_path)

    # Security check: ensure path is within worktree
    full_path_resolved = Path(full_path).resolve()
    worktree_resolved = Path(task.worktree_path).resolve()
    if not str(full_path_resolved).startswith(str(worktree_resolved)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path (outside worktree)"
        )

    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}"
        )

    if not os.path.isfile(full_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a file"
        )

    result = FileService.get_file_hash(task.worktree_path, file_path)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    return {"hash": result["hash"]}


@router.get("/{task_id}/files/{file_path:path}")
async def read_file(
    task_id: str,
    file_path: str,
    raw: bool = Query(False, description="Return raw file content for binary files"),
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Read file content

    If raw=true is passed, returns raw binary content for binary files like PDF.
    Otherwise returns text content as JSON.
    """
    import os
    from urllib.parse import unquote

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # URL decode the file path
    file_path = unquote(file_path)
    full_path = os.path.join(task.worktree_path, file_path)

    # Security check: ensure path is within worktree
    full_path_resolved = Path(full_path).resolve()
    worktree_resolved = Path(task.worktree_path).resolve()
    if not str(full_path_resolved).startswith(str(worktree_resolved)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path (outside worktree)"
        )

    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {full_path}"
        )

    # Return raw file content for binary files
    if raw:
        media_type = get_media_type(file_path)
        print(f"[DEBUG] Raw file request: path={file_path}, full_path={full_path}, media_type={media_type}")
        return FileResponse(
            full_path,
            media_type=media_type,
            filename=os.path.basename(file_path)
        )

    # Otherwise return text content
    success, content, error = FileService.read_file(task.worktree_path, file_path)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if error else status.HTTP_404_NOT_FOUND,
            detail=error or "File not found"
        )

    # Get hash for cache validation
    hash_result = FileService.get_file_hash(task.worktree_path, file_path)
    file_hash = hash_result["hash"] if hash_result["success"] else None

    return {"content": content, "hash": file_hash}


@router.put("/{task_id}/files/{file_path:path}")
async def write_file(
    task_id: str,
    file_path: str,
    file_data: FileWrite,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Write file content"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    success, error = FileService.write_file(task.worktree_path, file_path, file_data.content)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return {"success": True}


@router.delete("/{task_id}/files/{file_path:path}", response_model=FileDeleteResponse)
async def delete_file(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    session: Session = Depends(require_auth)
):
    """Delete a file or directory"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    success, error = FileService.delete_file(task.worktree_path, file_path)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return {"success": True}


@router.get("/{task_id}/changed-files", response_model=ChangedFilesResponse)
async def get_changed_files(
    task_id: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get list of changed files in task with Git status"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    files = GitService.get_changed_files_with_status(task.worktree_path)

    return {"files": files}


@router.get("/{task_id}/diff/{file_path:path}")
async def get_file_diff(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get diff for a specific file (returns git diff output)"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Check file size
    is_within_limit, size, size_formatted = check_file_size(task.worktree_path, file_path)
    if not is_within_limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large to display ({size_formatted})"
        )

    # Get project for main branch
    from app.models import Project
    project = db.query(Project).filter(Task.id == task.project_id).first()

    base_branch = project.main_branch if project else "main"
    diff = GitService.get_file_diff(task.worktree_path, file_path, base_branch)

    return {"diff": diff}


@router.get("/{task_id}/original/{file_path:path}")
async def get_original_file(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Get original file content from worktree HEAD for diff comparison"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Check file size
    is_within_limit, size, size_formatted = check_file_size(task.worktree_path, file_path)
    if not is_within_limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large to display ({size_formatted})"
        )

    # Get original content from worktree HEAD (last committed state)
    # This compares working directory changes against the last commit on the branch
    original_content = GitService.get_file_from_worktree_head(
        task.worktree_path,
        file_path
    )

    return {"content": original_content}


@router.post("/{task_id}/revert/{file_path:path}")
async def revert_file(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Revert a file to its last committed state"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    success, message, is_tracked = GitService.revert_file(
        task.worktree_path,
        file_path
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {
        "success": True,
        "message": message,
        "is_tracked": is_tracked
    }


@router.post("/{task_id}/stage/{file_path:path}")
async def stage_file(
    task_id: str,
    file_path: str,
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """Stage a file (git add) to mark conflicts as resolved"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    success, message = GitService.stage_file(
        task.worktree_path,
        file_path
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {
        "success": True,
        "message": message
    }


@router.post("/{task_id}/files/upload")
async def upload_files(
    task_id: str,
    files: List[UploadFile],
    target_path: str = Form("", description="Target directory path (relative to worktree)"),
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """
    Upload files to a task worktree directory.

    Args:
        task_id: Task ID
        files: List of files to upload (multipart/form-data)
        target_path: Target directory path (empty string for worktree root)

    Returns:
        FileUploadResponse with results for each file
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Build target directory path
    if target_path:
        target_dir = Path(task.worktree_path) / target_path
        # Security check: ensure path is within worktree
        target_dir_resolved = target_dir.resolve()
        worktree_resolved = Path(task.worktree_path).resolve()
        if not str(target_dir_resolved).startswith(str(worktree_resolved)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target path (outside worktree)"
            )
    else:
        target_dir = Path(task.worktree_path)

    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)

    results = []
    uploaded = 0
    failed = 0

    for file in files:
        try:
            # Sanitize filename to prevent path traversal
            filename = file.filename or "unnamed_file"
            # Check for path traversal in filename
            if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
                logger.warning(f"Invalid filename detected: {filename}")
                results.append({
                    "filename": filename,
                    "success": False,
                    "error": "Invalid filename"
                })
                failed += 1
                continue

            file_path = target_dir / filename
            logger.info(f"Uploading file {filename} to {file_path}")

            # Write file content
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            logger.info(f"Successfully uploaded {filename} ({len(content)} bytes)")
            results.append({
                "filename": filename,
                "success": True,
                "error": None
            })
            uploaded += 1

        except Exception as e:
            logger.error(f"Failed to upload file {file.filename}: {e}")
            results.append({
                "filename": file.filename or "unnamed_file",
                "success": False,
                "error": str(e)
            })
            failed += 1

    return {
        "success": uploaded > 0,
        "results": results,
        "total": len(files),
        "uploaded": uploaded,
        "failed": failed
    }


@router.post("/{task_id}/upload-temp", response_model=TempUploadResponse)
async def upload_to_temp(
    task_id: str,
    files: List[UploadFile] = Form(...),
    db: DBSession = Depends(get_db),
    current_user: Task = Depends(require_auth)
):
    """
    Upload files to a temporary directory.
    Returns paths for user to reference in terminal.

    Files are saved to /tmp/vibe2crazy-upload/{task_id}/ by default.
    Maximum file size is 100MB by default (configurable via MAX_UPLOAD_SIZE env var).
    """
    # Verify task exists
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Create task-specific temp directory
    task_temp_dir = os.path.join(TEMP_UPLOAD_DIR, task_id)
    os.makedirs(task_temp_dir, exist_ok=True)

    results = []
    uploaded = 0
    failed = 0

    for file in files:
        try:
            # Read file content
            content = await file.read()
            filename = file.filename or "file"

            # Check file size
            if len(content) > MAX_UPLOAD_SIZE:
                results.append(TempUploadResult(
                    filename=filename,
                    path="",
                    size=len(content),
                    success=False,
                    error=f"File too large (max {MAX_UPLOAD_SIZE // (1024*1024)}MB)"
                ))
                failed += 1
                continue

            # Generate unique filename
            safe_filename = FileService.generate_unique_filename(task_temp_dir, filename)
            file_path = os.path.join(task_temp_dir, safe_filename)

            # Save file
            with open(file_path, 'wb') as f:
                f.write(content)

            results.append(TempUploadResult(
                filename=safe_filename,
                path=file_path,
                size=len(content),
                success=True
            ))
            uploaded += 1
            logger.info(f"Uploaded temp file: {file_path} ({len(content)} bytes)")

        except Exception as e:
            logger.error(f"Failed to upload file {file.filename}: {e}")
            results.append(TempUploadResult(
                filename=file.filename or "file",
                path="",
                size=0,
                success=False,
                error=str(e)
            ))
            failed += 1

    return TempUploadResponse(
        success=uploaded > 0,
        results=results,
        temp_dir=task_temp_dir,
        total=len(files),
        uploaded=uploaded,
        failed=failed
    )