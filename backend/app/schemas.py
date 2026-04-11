from pydantic import BaseModel, Field, field_serializer
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from app.models import TaskStatus, TaskStatusType, CodeStatusType


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


class SessionResponse(BaseModel):
    authenticated: bool
    expires_at: Optional[datetime] = None


class ProjectBase(BaseModel):
    name: str
    git_path: str
    main_branch: str = "main"


class ProjectCreate(ProjectBase):
    init_git: Optional[bool] = False
    create_directory: Optional[bool] = False


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    main_branch: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    name: str


class TaskCreate(TaskBase):
    direct_on_branch: bool = False


class TaskResponse(TaskBase):
    id: str
    project_id: str
    branch_name: str
    worktree_path: str
    tmux_session: str
    status: TaskStatus
    task_status: TaskStatusType
    code_status: CodeStatusType
    last_task_status_check: Optional[datetime] = None
    last_code_status_check: Optional[datetime] = None
    last_merge_commit_hash: Optional[str] = None
    extra_index_paths: Optional[str] = None
    direct_on_branch: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[TaskStatus] = None
    extra_index_paths: Optional[str] = None


class FileNode(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    children: Optional[list["FileNode"]] = None


class FileRead(BaseModel):
    content: str


class FileWrite(BaseModel):
    content: str


class FileDeleteResponse(BaseModel):
    success: bool


class ChangedFileInfo(BaseModel):
    """Single changed file with status"""
    path: str
    status: str  # Git status code: A, M, D, R, C, T, ?


class ChangedFilesResponse(BaseModel):
    """Response for changed files endpoint with status"""
    files: List[ChangedFileInfo]


class PaginatedChangedFilesResponse(BaseModel):
    """Paginated response for changed files endpoint"""
    files: List[ChangedFileInfo]
    total: int
    page: int
    page_size: int
    total_pages: int


class AcceptRequest(BaseModel):
    message: Optional[str] = "Accept changes"


class AcceptResponse(BaseModel):
    success: bool
    message: str
    commit_hash: Optional[str] = None


class TaskStatusResponse(BaseModel):
    task_status: TaskStatusType
    code_status: CodeStatusType
    last_task_status_check: Optional[datetime] = None
    last_code_status_check: Optional[datetime] = None


class ButtonStatesResponse(BaseModel):
    """Response for button states"""
    can_accept: bool
    can_merge: bool
    reason: Optional[str] = None


class MergeRequest(BaseModel):
    message: str = "Merge task"


class CommandExecution(BaseModel):
    """Details of a git command execution for debugging"""
    command: str  # Full command that was executed
    exit_code: int  # Process exit code (0 = success)
    stdout: str = ""  # Standard output
    stderr: str = ""  # Standard error output
    working_dir: str = ""  # Working directory where command ran


class MergeResponse(BaseModel):
    success: bool
    message: str
    conflicts: Optional[str] = None
    needs_resolution: bool = False  # NEW: Indicates sync has conflicts that need resolution
    execution_log: Optional[List["CommandExecution"]] = None  # Detailed command execution log for debugging


class RevertResponse(BaseModel):
    success: bool
    message: str
    is_tracked: bool  # Whether file was Git tracked


class FileUploadItem(BaseModel):
    """Single file upload result"""
    filename: str
    success: bool
    error: Optional[str] = None


class FileUploadResponse(BaseModel):
    """Response for file upload endpoint"""
    success: bool
    results: List[FileUploadItem]
    total: int
    uploaded: int
    failed: int


class TempUploadResult(BaseModel):
    """Single file upload result for temp directory uploads"""
    filename: str
    path: str
    size: int
    success: bool = True
    error: Optional[str] = None


class TempUploadResponse(BaseModel):
    """Response for temp file upload endpoint"""
    success: bool
    results: List[TempUploadResult]
    temp_dir: str
    total: int
    uploaded: int
    failed: int


class CommitFileSchema(BaseModel):
    path: str
    status: str  # 'A', 'M', 'D'
    additions: int
    deletions: int


class CommitSchema(BaseModel):
    hash: str
    date: str
    message: str
    files: List[CommitFileSchema]


class PaginatedCommitsSchema(BaseModel):
    items: List[CommitSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


class CommitFileDiffSchema(BaseModel):
    path: str
    status: str  # 'A', 'M', 'D'
    original: str
    modified: str


class CommitDiffSchema(BaseModel):
    hash: str
    date: str
    message: str
    files: List[CommitFileDiffSchema]


class ErrorResponse(BaseModel):
    detail: str


class DiffResponse(BaseModel):
    diff: str


class CommandQueueBase(BaseModel):
    content: str


class CommandQueueCreate(CommandQueueBase):
    pass


class CommandQueueResponse(BaseModel):
    id: str
    task_id: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime
    executed_at: Optional[datetime] = None

    @field_serializer('created_at', 'updated_at', 'executed_at')
    def serialize_datetime(self, value: Optional[datetime], _info) -> Optional[str]:
        if value is None:
            return None
        # If datetime has no timezone info, assume it's local time (system timezone)
        # and attach timezone info for proper serialization
        if value.tzinfo is None:
            # Get system timezone offset (CST = UTC+8)
            # We'll use UTC+8 since this is the expected timezone for the system
            local_tz = timezone(timedelta(hours=8))
            value = value.replace(tzinfo=local_tz)
        return value.isoformat()

    class Config:
        from_attributes = True


# Symbol preview schemas
class IndexRequest(BaseModel):
    task_id: str
    force: bool = False


class IndexProgress(BaseModel):
    files_scanned: int
    total_files: int
    symbols_found: int


class IndexResponse(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None
    cached: bool = False
    indexed_files: Optional[int] = None
    indexed_symbols: Optional[int] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    suggestion: Optional[str] = None
    progress: Optional[IndexProgress] = None


class SymbolMatchItem(BaseModel):
    """A single symbol match for disambiguation"""
    file_path: str
    line_number: int
    kind: str
    signature: Optional[str] = None


class SymbolDetailRequest(BaseModel):
    """Request for symbol details at a specific location"""
    file_path: str
    line_number: int
    task_id: str


class SymbolDefinitionResponse(BaseModel):
    found: bool
    name: Optional[str] = None
    kind: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    type_signature: Optional[str] = None
    signature_file_path: Optional[str] = None
    signature_line_number: Optional[int] = None
    docstring: Optional[str] = None
    definition_snippet: Optional[List[str]] = None
    snippet_highlight_index: Optional[int] = None
    reason: Optional[str] = None
    message: Optional[str] = None
    similar_symbols: Optional[List[str]] = None
    matches: Optional[List[SymbolMatchItem]] = None


# Tunnel schemas
class TunnelStatusResponse(BaseModel):
    """Tunnel status response."""
    status: str
    remote_url: Optional[str] = None
    token: Optional[str] = None
    last_error: Optional[str] = None
    server_url: Optional[str] = None


class TunnelConfigUpdate(BaseModel):
    """Tunnel configuration update request."""
    token: str
    use_tls: Optional[bool] = True
    verify_tls: Optional[bool] = False


class TunnelConfigResponse(BaseModel):
    """Tunnel configuration response."""
    success: bool
    message: str


# Network detection schemas
class LocalInfoResponse(BaseModel):
    """Response for /api/tunnel/localinfo endpoint."""
    ips: List[str]
    port: int
    token_hash: str


class TokenHashResponse(BaseModel):
    """Response for /api/tunnel/token_hash endpoint."""
    token_hash: str


