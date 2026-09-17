"""
NotebookService - Markdown notebook backed by real files on disk.

A note is a plain ``.md`` file under a configurable root (``settings.notebooks_path``).
A "group" is a direct subdirectory of that root. SQLite stores only metadata
(pin flag, ordering, cached stat) - the filesystem is the source of truth, and
``reconcile()`` keeps the index in step with it.

Conventions follow the other services: every method is a ``@staticmethod`` and
receives the request's ``db`` session. The service owns its commits.
"""

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Notebook, NotebookGroup

logger = logging.getLogger(__name__)

DEFAULT_GROUP_NAME = "Unsorted"
POSITION_STEP = 1024
# Tolerance when deciding whether the cached size/mtime need refreshing for
# display. It absorbs the microsecond rounding of the SQLite round-trip, and is
# not a correctness bound - content conflicts are detected by hash.
STAT_REFRESH_TOLERANCE = 1.0  # seconds

MAX_NAME_LEN = 120
MAX_CONTENT_BYTES = 2 * 1024 * 1024  # write limit

# Search guards: keep a runaway notebook root from blocking the request thread.
MAX_SEARCH_FILES = 500  # files whose *content* we actually read
MAX_SEARCH_ENTRIES = 5000  # hard cap on directory entries inspected (name matches)
MAX_SEARCH_FILE_BYTES = 256 * 1024  # larger files are matched on name only
SNIPPET_RADIUS = 40

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")
RESERVED_WINDOWS = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class StaleContentError(Exception):
    """The file changed on disk since the client last read it (optimistic lock)."""


# ---------------------------------------------------------------------------
# mtime helpers
#
# SQLite hands back naive datetimes, so we normalise on the way in and out:
# everything in the DB is naive UTC, and epoch seconds is the wire format.
# ---------------------------------------------------------------------------

def _to_db_mtime(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)


def _from_db_mtime(value: Optional[datetime]) -> Optional[float]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).timestamp()
    return value.timestamp()


def content_hash(text: str) -> str:
    """Optimistic-lock token for note content.

    A hash rather than an mtime: coarse filesystem timestamps (1s on some
    mounts, and on ext4 historically) cannot distinguish two edits within the
    same second, which is exactly the window where we would silently clobber
    an external edit. Same format as ``FileService.get_file_hash``.
    """
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


class NotebookService:
    """Notebook metadata index on top of a directory of .md files."""

    # -- paths ------------------------------------------------------------

    @staticmethod
    def root() -> Path:
        return settings.notebooks_path

    @staticmethod
    def sanitize_name(name: str, *, fallback: str = "untitled") -> str:
        """Turn user input into a safe file/directory name (no extension, no separators)."""
        name = unicodedata.normalize("NFC", name or "").strip()
        name = INVALID_CHARS.sub("_", name)
        name = WHITESPACE.sub(" ", name).strip()
        # Leading dots would hide the entry; trailing dots/spaces break on Windows.
        name = name.strip(". _")
        if name.upper() in RESERVED_WINDOWS:
            name = f"_{name}"
        if len(name) > MAX_NAME_LEN:
            name = name[:MAX_NAME_LEN].rstrip(". ")
        return name or fallback

    @staticmethod
    def _resolve(root: Path, group_name: str, filename: Optional[str] = None) -> Path:
        """Resolve (group, filename) to an absolute path, asserting it stays under root.

        This is the only place that joins user input onto the filesystem.
        """
        if not group_name or group_name in (".", "..") or "/" in group_name or "\\" in group_name:
            raise ValueError(f"Invalid group name: {group_name!r}")
        if filename is not None:
            if not filename or filename in (".", "..") or "/" in filename or "\\" in filename:
                raise ValueError(f"Invalid filename: {filename!r}")
            if not filename.lower().endswith(".md"):
                raise ValueError("Notebook file must end with .md")

        candidate = root / group_name / filename if filename is not None else root / group_name
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise ValueError("Path escapes notebook root")
        return resolved

    @staticmethod
    def _note_path(root: Path, note: Notebook) -> Path:
        return NotebookService._resolve(root, note.group.name, note.filename)

    # -- ordering ---------------------------------------------------------

    @staticmethod
    def _next_note_position(db: Session, group_id: str) -> int:
        current = db.query(func.max(Notebook.position)).filter(
            Notebook.group_id == group_id
        ).scalar()
        return (current or 0) + POSITION_STEP

    @staticmethod
    def _next_group_position(db: Session) -> int:
        current = db.query(func.max(NotebookGroup.position)).scalar()
        return (current or 0) + POSITION_STEP

    @staticmethod
    def _normalize_positions(db: Session, group_id: str) -> None:
        """Re-space a group's notes to 1024, 2048, ... when gaps run out."""
        notes = db.query(Notebook).filter(Notebook.group_id == group_id).order_by(
            Notebook.pinned.desc(), Notebook.position.asc(), Notebook.created_at.asc()
        ).all()
        for index, note in enumerate(notes, start=1):
            note.position = index * POSITION_STEP

    @staticmethod
    def _normalize_group_positions(db: Session) -> None:
        """Re-space groups, keeping the default group pinned at the front."""
        groups = db.query(NotebookGroup).order_by(
            NotebookGroup.position.asc(), NotebookGroup.created_at.asc()
        ).all()
        index = 0
        for group in groups:
            if group.is_default:
                group.position = 0
                continue
            index += 1
            group.position = index * POSITION_STEP

    # -- groups -----------------------------------------------------------

    @staticmethod
    def ensure_default_group(db: Session) -> NotebookGroup:
        group = db.query(NotebookGroup).filter(NotebookGroup.is_default.is_(True)).first()
        if group is None:
            group = NotebookGroup(name=DEFAULT_GROUP_NAME, position=0, is_default=True)
            db.add(group)
            db.commit()
            db.refresh(group)
            logger.info("Created default notebook group")
            return group

        if group.name != DEFAULT_GROUP_NAME:
            # The default group's name is a constant, and it doubles as its
            # directory. Bring an older name across so the two stay in step.
            root = NotebookService.root()
            old_path = root / group.name
            new_path = root / DEFAULT_GROUP_NAME
            if old_path.is_dir() and not new_path.exists():
                old_path.rename(new_path)
                logger.info(f"Renamed default group directory to '{DEFAULT_GROUP_NAME}'")
            elif old_path.is_dir():
                logger.warning(
                    f"Both '{group.name}' and '{DEFAULT_GROUP_NAME}' exist; "
                    f"leaving the directories alone"
                )
            group.name = DEFAULT_GROUP_NAME
            db.commit()
            db.refresh(group)

        return group

    @staticmethod
    def list_groups(db: Session) -> List[dict]:
        """Groups in display order, each with a note count."""
        counts = dict(
            db.query(Notebook.group_id, func.count(Notebook.id))
            .group_by(Notebook.group_id)
            .all()
        )
        groups = db.query(NotebookGroup).order_by(
            NotebookGroup.position.asc(), NotebookGroup.created_at.asc()
        ).all()
        return [
            {
                "id": g.id,
                "name": g.name,
                "position": g.position,
                "is_default": g.is_default,
                "note_count": counts.get(g.id, 0),
                "created_at": g.created_at,
                "updated_at": g.updated_at,
            }
            for g in groups
        ]

    @staticmethod
    def create_group(db: Session, name: str) -> NotebookGroup:
        root = NotebookService.root()
        safe_name = NotebookService.sanitize_name(name)

        if safe_name == DEFAULT_GROUP_NAME:
            raise FileExistsError(f"Group '{DEFAULT_GROUP_NAME}' already exists")

        existing = db.query(NotebookGroup).filter(
            func.lower(NotebookGroup.name) == safe_name.lower()
        ).first()
        if existing:
            raise FileExistsError(f"A group named '{safe_name}' already exists")

        path = NotebookService._resolve(root, safe_name)
        if path.exists():
            raise FileExistsError(f"'{safe_name}' already exists on disk")

        path.mkdir(parents=True, exist_ok=False)
        try:
            group = NotebookGroup(
                name=safe_name,
                position=NotebookService._next_group_position(db),
                is_default=False,
            )
            db.add(group)
            db.commit()
            db.refresh(group)
        except Exception:
            db.rollback()
            # Keep the index consistent with the disk: undo the directory.
            try:
                path.rmdir()
            except OSError:
                logger.warning(f"Could not roll back group directory {path}")
            raise
        logger.info(f"Created notebook group '{safe_name}'")
        return group

    @staticmethod
    def get_group(db: Session, group_id: str) -> NotebookGroup:
        group = db.query(NotebookGroup).filter(NotebookGroup.id == group_id).first()
        if group is None:
            raise FileNotFoundError("Group not found")
        return group

    @staticmethod
    def rename_group(db: Session, group_id: str, name: str) -> NotebookGroup:
        root = NotebookService.root()
        group = NotebookService.get_group(db, group_id)
        if group.is_default:
            raise ValueError(f"The '{DEFAULT_GROUP_NAME}' group cannot be renamed")

        safe_name = NotebookService.sanitize_name(name)
        if safe_name == group.name:
            return group
        if safe_name == DEFAULT_GROUP_NAME:
            raise FileExistsError(f"Group '{DEFAULT_GROUP_NAME}' already exists")

        clash = db.query(NotebookGroup).filter(
            func.lower(NotebookGroup.name) == safe_name.lower(),
            NotebookGroup.id != group.id,
        ).first()
        if clash:
            raise FileExistsError(f"A group named '{safe_name}' already exists")

        old_path = NotebookService._resolve(root, group.name)
        new_path = NotebookService._resolve(root, safe_name)
        if new_path.exists():
            raise FileExistsError(f"'{safe_name}' already exists on disk")

        if old_path.is_dir():
            old_path.rename(new_path)
        else:
            # Directory never materialised (group created but no notes yet).
            new_path.mkdir(parents=True, exist_ok=True)

        try:
            group.name = safe_name
            db.commit()
            db.refresh(group)
        except Exception:
            db.rollback()
            try:
                new_path.rename(old_path)
            except OSError:
                logger.error(f"Could not roll back group rename {new_path} -> {old_path}")
            raise
        logger.info(f"Renamed notebook group to '{safe_name}'")
        return group

    @staticmethod
    def delete_group(db: Session, group_id: str, force: bool = False) -> None:
        root = NotebookService.root()
        group = NotebookService.get_group(db, group_id)
        if group.is_default:
            raise ValueError(f"The '{DEFAULT_GROUP_NAME}' group cannot be deleted")

        note_count = db.query(func.count(Notebook.id)).filter(
            Notebook.group_id == group.id
        ).scalar() or 0
        path = NotebookService._resolve(root, group.name)
        has_files = path.is_dir() and any(
            p.is_file() and p.suffix.lower() == ".md" and not p.name.startswith(".")
            for p in path.iterdir()
        )

        if (note_count or has_files) and not force:
            raise FileExistsError("Group is not empty")

        if path.is_dir():
            for item in path.iterdir():
                if item.is_file():
                    item.unlink()
            try:
                path.rmdir()
            except OSError:
                # Leftover subdirectories we do not manage - keep the group.
                logger.warning(f"Group directory {path} is not empty, leaving it in place")

        db.delete(group)
        db.commit()
        logger.info(f"Deleted notebook group '{group.name}'")

    @staticmethod
    def move_group(db: Session, group_id: str, direction: str) -> List[dict]:
        group = NotebookService.get_group(db, group_id)
        if direction not in ("up", "down"):
            raise ValueError("direction must be 'up' or 'down'")

        # The default group never participates in reordering: it has no
        # is_default siblings, so any move raises "Already at the boundary".
        siblings = db.query(NotebookGroup).filter(
            NotebookGroup.id != group.id,
            NotebookGroup.is_default.is_(group.is_default),
        )

        if direction == "up":
            neighbor = siblings.filter(NotebookGroup.position < group.position).order_by(
                NotebookGroup.position.desc()
            ).first()
        else:
            neighbor = siblings.filter(NotebookGroup.position > group.position).order_by(
                NotebookGroup.position.asc()
            ).first()

        if neighbor is None:
            raise ValueError("Already at the boundary")

        if abs(group.position - neighbor.position) < 2:
            NotebookService._normalize_group_positions(db)

        group.position, neighbor.position = neighbor.position, group.position
        db.commit()
        return NotebookService.list_groups(db)

    # -- reading the tree -------------------------------------------------

    @staticmethod
    def reconcile(db: Session) -> Dict[str, int]:
        """Align the metadata index with what is actually on disk.

        The filesystem wins. Called on every list request so notes added or
        removed outside the app (terminal, editor, git) show up.
        """
        root = NotebookService.root()
        root.mkdir(parents=True, exist_ok=True)
        created = updated = deleted = 0

        default_group = NotebookService.ensure_default_group(db)

        # Symlinks are excluded: _resolve() rejects any path that resolves outside
        # the root, so adopting a symlinked directory here would index a group
        # that every subsequent read then refuses.
        disk_group_names = {
            p.name for p in root.iterdir()
            if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")
        }
        disk_group_names.discard(DEFAULT_GROUP_NAME)

        db_groups: Dict[str, NotebookGroup] = {
            g.name: g for g in db.query(NotebookGroup).all()
        }

        # Directories with no DB row -> adopt them as groups. Positions are
        # tracked locally because pending inserts are not visible to func.max().
        adopted = sorted(disk_group_names - set(db_groups))
        next_group_position = NotebookService._next_group_position(db)
        for name in adopted:
            next_group_position += POSITION_STEP
            group = NotebookGroup(name=name, position=next_group_position, is_default=False)
            db.add(group)
            db_groups[name] = group
            created += 1
        if adopted:
            db.flush()

        # Per-group file scan.
        for name, group in list(db_groups.items()):
            group_dir = root / name
            disk_files: Dict[str, Path] = {}
            if group_dir.is_dir():
                disk_files = {
                    p.name: p for p in group_dir.iterdir()
                    if p.is_file() and not p.is_symlink()
                    and p.suffix.lower() == ".md" and not p.name.startswith(".")
                }

            db_notes: Dict[str, Notebook] = {
                n.filename: n for n in db.query(Notebook)
                .filter(Notebook.group_id == group.id).all()
            }

            next_position = NotebookService._next_note_position(db, group.id)
            for filename in sorted(set(disk_files) - set(db_notes)):
                path = disk_files[filename]
                stat = path.stat()
                next_position += POSITION_STEP
                db.add(Notebook(
                    title=path.stem,
                    filename=filename,
                    group_id=group.id,
                    position=next_position,
                    pinned=False,
                    size=stat.st_size,
                    mtime=_to_db_mtime(stat.st_mtime),
                ))
                created += 1

            for filename in set(db_notes) - set(disk_files):
                db.delete(db_notes[filename])
                deleted += 1

            for filename in set(db_notes) & set(disk_files):
                note = db_notes[filename]
                stat = disk_files[filename].stat()
                cached = _from_db_mtime(note.mtime) or 0.0
                if note.size != stat.st_size \
                        or abs(cached - stat.st_mtime) > STAT_REFRESH_TOLERANCE:
                    note.size = stat.st_size
                    note.mtime = _to_db_mtime(stat.st_mtime)
                    updated += 1

        db.flush()

        # Groups whose directory is gone (and are not the default) are dropped.
        for name, group in db_groups.items():
            if group.is_default or name in disk_group_names:
                continue
            db.delete(group)
            deleted += 1

        if created or updated or deleted:
            db.commit()
            logger.info(
                f"Notebook reconcile: +{created} ~{updated} -{deleted}"
            )
        return {"created": created, "updated": updated, "deleted": deleted}

    @staticmethod
    def list_notes(db: Session) -> Dict[str, list]:
        root = NotebookService.root()
        groups = db.query(NotebookGroup).order_by(
            NotebookGroup.position.asc(), NotebookGroup.created_at.asc()
        ).all()

        result = []
        for group in groups:
            notes = db.query(Notebook).filter(Notebook.group_id == group.id).order_by(
                Notebook.pinned.desc(), Notebook.position.asc(), Notebook.created_at.asc()
            ).all()
            result.append({
                "id": group.id,
                "name": group.name,
                "position": group.position,
                "is_default": group.is_default,
                "note_count": len(notes),
                "notes": [NotebookService.note_payload(n) for n in notes],
            })
        return {"root": str(root), "groups": result}

    @staticmethod
    def note_payload(note: Notebook) -> dict:
        # No `updated_at`: it is stored as naive UTC, so any client parsing it
        # would silently apply its own offset. `mtime` is epoch seconds instead.
        return {
            "id": note.id,
            "title": note.title,
            "filename": note.filename,
            "group_id": note.group_id,
            "position": note.position,
            "pinned": note.pinned,
            "size": note.size,
            "mtime": _from_db_mtime(note.mtime),
        }

    @staticmethod
    def get_note(db: Session, note_id: str) -> Notebook:
        note = db.query(Notebook).filter(Notebook.id == note_id).first()
        if note is None:
            raise FileNotFoundError("Note not found")
        return note

    @staticmethod
    def read_note(db: Session, note_id: str) -> dict:
        root = NotebookService.root()
        note = NotebookService.get_note(db, note_id)
        path = NotebookService._note_path(root, note)
        if not path.is_file():
            # The index is stale - the file is gone.
            raise FileNotFoundError("Note file no longer exists on disk")

        content = NotebookService._read_file_text(path)

        stat = path.stat()
        payload = NotebookService.note_payload(note)
        payload["content"] = content
        payload["size"] = stat.st_size
        payload["mtime"] = stat.st_mtime
        # The client hands this back on save so an external edit is detected.
        payload["hash"] = content_hash(content)
        payload["group_name"] = note.group.name
        return payload

    @staticmethod
    def _read_file_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="replace")

    # -- writing notes ----------------------------------------------------

    @staticmethod
    def create_note(db: Session, group_id: str, title: str, content: str = "") -> Notebook:
        root = NotebookService.root()
        group = NotebookService.get_group(db, group_id)

        safe_title = NotebookService.sanitize_name(title, fallback="untitled")
        filename = f"{safe_title}.md"
        path = NotebookService._resolve(root, group.name, filename)

        if path.exists():
            raise FileExistsError(f"A note named '{safe_title}' already exists")
        clash = db.query(Notebook).filter(
            Notebook.group_id == group.id,
            func.lower(Notebook.filename) == filename.lower(),
        ).first()
        if clash:
            raise FileExistsError(f"A note named '{safe_title}' already exists")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        try:
            note = Notebook(
                title=safe_title,
                filename=filename,
                group_id=group.id,
                position=NotebookService._next_note_position(db, group.id),
                pinned=False,
                size=path.stat().st_size,
                mtime=_to_db_mtime(path.stat().st_mtime),
            )
            db.add(note)
            db.commit()
            db.refresh(note)
        except Exception:
            db.rollback()
            try:
                path.unlink()
            except OSError:
                logger.warning(f"Could not roll back note file {path}")
            raise
        logger.info(f"Created note '{filename}' in group '{group.name}'")
        return note

    @staticmethod
    def save_content(
        db: Session, note_id: str, content: str, base_hash: Optional[str] = None
    ) -> dict:
        root = NotebookService.root()
        note = NotebookService.get_note(db, note_id)
        path = NotebookService._note_path(root, note)

        if not path.is_file():
            raise FileNotFoundError("Note file no longer exists on disk")

        encoded_size = len(content.encode("utf-8"))
        if encoded_size > MAX_CONTENT_BYTES:
            raise ValueError("Note content is too large")

        if base_hash is not None:
            on_disk = content_hash(NotebookService._read_file_text(path))
            if on_disk != base_hash:
                raise StaleContentError("The file was modified externally. Reload required.")

        path.write_text(content, encoding="utf-8")
        stat = path.stat()
        note.size = stat.st_size
        note.mtime = _to_db_mtime(stat.st_mtime)
        db.commit()
        db.refresh(note)

        return {
            "id": note.id,
            "size": note.size,
            "mtime": stat.st_mtime,
            "hash": content_hash(content),
        }

    @staticmethod
    def update_note(
        db: Session,
        note_id: str,
        title: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Notebook:
        """Rename and/or move a note. Both are a file move plus an index update."""
        root = NotebookService.root()
        note = NotebookService.get_note(db, note_id)

        target_group = note.group
        if group_id is not None and group_id != note.group_id:
            target_group = NotebookService.get_group(db, group_id)

        new_title = NotebookService.sanitize_name(title, fallback="untitled") \
            if title is not None else note.title
        new_filename = f"{new_title}.md"

        unchanged = new_title == note.title and target_group.id == note.group_id
        if unchanged:
            return note

        old_path = NotebookService._note_path(root, note)
        new_path = NotebookService._resolve(root, target_group.name, new_filename)

        if new_path != old_path:
            if new_path.exists():
                raise FileExistsError(f"A note named '{new_title}' already exists")
            clash = db.query(Notebook).filter(
                Notebook.group_id == target_group.id,
                func.lower(Notebook.filename) == new_filename.lower(),
                Notebook.id != note.id,
            ).first()
            if clash:
                raise FileExistsError(f"A note named '{new_title}' already exists")

            if not old_path.is_file():
                raise FileNotFoundError("Note file no longer exists on disk")

            new_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.rename(new_path)

        try:
            note.title = new_title
            note.filename = new_filename
            if target_group.id != note.group_id:
                note.group_id = target_group.id
                # Land at the end of the destination group.
                note.position = NotebookService._next_note_position(db, target_group.id)
                note.pinned = False
            db.commit()
            db.refresh(note)
        except Exception:
            db.rollback()
            if new_path != old_path:
                try:
                    new_path.rename(old_path)
                except OSError:
                    logger.error(f"Could not roll back note move {new_path} -> {old_path}")
            raise
        logger.info(f"Updated note '{new_filename}'")
        return note

    @staticmethod
    def delete_note(db: Session, note_id: str) -> None:
        root = NotebookService.root()
        note = NotebookService.get_note(db, note_id)
        path = NotebookService._note_path(root, note)
        if path.is_file():
            path.unlink()
        db.delete(note)
        db.commit()
        logger.info(f"Deleted note '{note.filename}'")

    @staticmethod
    def set_pinned(db: Session, note_id: str, pinned: bool) -> Notebook:
        note = NotebookService.get_note(db, note_id)
        note.pinned = pinned
        db.commit()
        db.refresh(note)
        return note

    @staticmethod
    def move_note(db: Session, note_id: str, direction: str) -> List[dict]:
        """Swap with the adjacent note in the same group and pin bucket."""
        note = NotebookService.get_note(db, note_id)
        if direction not in ("up", "down"):
            raise ValueError("direction must be 'up' or 'down'")

        siblings = db.query(Notebook).filter(
            Notebook.group_id == note.group_id,
            Notebook.pinned.is_(note.pinned),
            Notebook.id != note.id,
        )
        if direction == "up":
            neighbor = siblings.filter(Notebook.position < note.position).order_by(
                Notebook.position.desc(), Notebook.created_at.desc()
            ).first()
        else:
            neighbor = siblings.filter(Notebook.position > note.position).order_by(
                Notebook.position.asc(), Notebook.created_at.asc()
            ).first()

        if neighbor is None:
            raise ValueError("Already at the boundary")

        if abs(note.position - neighbor.position) < 2:
            NotebookService._normalize_positions(db, note.group_id)
            db.flush()

        note.position, neighbor.position = neighbor.position, note.position
        db.commit()
        return NotebookService.list_group_notes(db, note.group_id)

    @staticmethod
    def list_group_notes(db: Session, group_id: str) -> List[dict]:
        notes = db.query(Notebook).filter(Notebook.group_id == group_id).order_by(
            Notebook.pinned.desc(), Notebook.position.asc(), Notebook.created_at.asc()
        ).all()
        return [NotebookService.note_payload(n) for n in notes]

    # -- search -----------------------------------------------------------

    @staticmethod
    def search(db: Session, query: str, limit: int = 50) -> dict:
        """Search note names and contents. Filename hits rank before content hits."""
        root = NotebookService.root()
        term = (query or "").strip()
        if not term:
            return {"results": [], "total": 0, "truncated": False}
        needle = term.lower()

        # Map (group, filename) -> note id so results are directly openable.
        id_by_key = {
            (n.group.name, n.filename): n.id
            for n in db.query(Notebook).all()
        }

        name_hits: List[dict] = []
        content_hits: List[dict] = []
        reads = 0
        inspected = 0
        truncated = False

        if not root.is_dir():
            return {"results": [], "total": 0, "truncated": False}

        for group_dir in sorted(
            (p for p in root.iterdir()
             if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")),
            key=lambda p: p.name,
        ):
            for path in sorted(group_dir.iterdir(), key=lambda p: p.name):
                if not path.is_file() or path.is_symlink() \
                        or path.suffix.lower() != ".md" or path.name.startswith("."):
                    continue
                if inspected >= MAX_SEARCH_ENTRIES:
                    truncated = True
                    break
                inspected += 1

                note_id = id_by_key.get((group_dir.name, path.name))
                if note_id is None:
                    continue

                base = {
                    "id": note_id,
                    "title": path.stem,
                    "filename": path.name,
                    "group_name": group_dir.name,
                }

                if needle in path.name.lower():
                    name_hits.append({**base, "match_type": "filename", "snippet": None, "line": None})
                    continue  # A name hit is enough; skip reading the file.

                try:
                    if path.stat().st_size > MAX_SEARCH_FILE_BYTES:
                        continue
                except OSError:
                    continue

                # Only files we actually read count against the read budget.
                if reads >= MAX_SEARCH_FILES:
                    truncated = True
                    break
                reads += 1

                try:
                    text = NotebookService._read_file_text(path)
                except OSError:
                    continue

                index = text.lower().find(needle)
                if index >= 0:
                    start = max(0, index - SNIPPET_RADIUS)
                    end = index + len(term) + SNIPPET_RADIUS
                    content_hits.append({
                        **base,
                        "match_type": "content",
                        "snippet": text[start:end],
                        "line": text.count("\n", 0, index) + 1,
                    })
            if truncated:
                break

        merged = name_hits + content_hits
        return {
            "results": merged[:limit],
            "total": len(merged),
            "truncated": truncated,
        }
