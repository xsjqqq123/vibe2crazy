import logging
import subprocess
import hashlib
import json
from pathlib import Path
from typing import List, Optional
import os

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = Path("/tmp")
CACHE_TTL = 3600  # 1小时


def path_similarity(path1: str, path2: str) -> int:
    """
    计算两个路径的相似度。
    返回共同路径段的数量。
    """
    if not path1 or not path2:
        return 0
    parts1 = Path(path1).parts
    parts2 = Path(path2).parts

    # 计算共同前缀长度
    common = 0
    for i in range(min(len(parts1), len(parts2))):
        if parts1[i] == parts2[i]:
            common += 1
        else:
            break
    return common

class GrepService:
    """Service for ripgrep-based code search"""

    @staticmethod
    def _get_cache_path(task_id: str, query: str, page: int) -> Path:
        """生成缓存文件路径"""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        return CACHE_DIR / f"referer_cache_{task_id}_{query_hash}_{page}.json"

    @staticmethod
    def _read_cache(cache_path: Path) -> Optional[dict]:
        """读取缓存"""
        if not cache_path.exists():
            return None
        # 检查过期
        age = cache_path.stat().st_mtime
        import time
        if time.time() - age > CACHE_TTL:
            cache_path.unlink()
            return None
        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def _write_cache(cache_path: Path, data: dict):
        """写入缓存"""
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to write cache: {e}")

    @staticmethod
    def search(task_id: str, worktree_path: str, query: str, page: int = 1, per_page: int = 20, current_file: str = None) -> dict:
        """
        执行 ripgrep 搜索
        Returns: {
            "results": [{"file": str, "line": int, "content": str}],
            "groups": [{"file": str, "matches": [{"line": int, "content": str}]}],
            "total": int,
            "cached": bool
        }
        """
        # 将 current_file 转为绝对路径
        if current_file and not current_file.startswith('/'):
            current_file = os.path.join(worktree_path, current_file)

        # 全量缓存键（使用 task_id 确保唯一性）
        full_cache_path = GrepService._get_cache_path(task_id, query, 0)

        # 尝试读取全量缓存
        cached = GrepService._read_cache(full_cache_path)

        if not cached:
            # 执行 ripgrep
            try:
                cmd = [
                    "rg", "--json", "-n", "-i",
                    "-g", "!node_modules",
                    "-g", "!node_modules/**",
                    "-g", "!.git",
                    "-g", "!.git/**",
                    query, worktree_path
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode not in (0, 1):  # 0=找到, 1=未找到
                    logger.error(f"ripgrep failed: {result.stderr}")
                    return {"results": [], "groups": [], "total": 0, "cached": False}

                # 解析 JSON 输出
                matches: List[dict] = []
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "match":
                            data = obj["data"]
                            matches.append({
                                "file": data["path"]["text"],
                                "line": data["line_number"],
                                "content": data["lines"]["text"].rstrip('\n')
                            })
                    except Exception:
                        continue

                # 写入全量缓存
                GrepService._write_cache(full_cache_path, {"matches": matches})

            except subprocess.TimeoutExpired:
                logger.error("ripgrep timed out")
                return {"results": [], "groups": [], "total": 0, "cached": False, "error": "Search timed out"}
            except Exception as e:
                logger.error(f"ripgrep error: {e}")
                return {"results": [], "groups": [], "total": 0, "cached": False, "error": str(e)}
        else:
            matches = cached["matches"]

        total = len(matches)

        # 按文件分组
        file_matches: dict = {}
        for m in matches:
            f = m["file"]
            if f not in file_matches:
                file_matches[f] = {"file": f, "matches": []}
            file_matches[f]["matches"].append({"line": m["line"], "content": m["content"]})
        groups = list(file_matches.values())

        # 按与当前文件的相似度排序（相似度高的排前面）
        if current_file:
            groups = sorted(groups, key=lambda g: -path_similarity(g["file"], current_file))

        # 分页：按文件数分页
        total_files = len(groups)
        start = (page - 1) * per_page
        end = start + per_page
        page_groups = groups[start:end]

        # 收集该页文件的所有匹配
        page_files = {g["file"] for g in page_groups}
        page_results = [m for m in matches if m["file"] in page_files]
        # 限制每文件只显示前3条
        limited_results = []
        file_count = {}
        for m in page_results:
            f = m["file"]
            file_count[f] = file_count.get(f, 0) + 1
            if file_count[f] <= 5:
                limited_results.append(m)

        return {
            "results": limited_results,
            "groups": page_groups,
            "total": total_files,  # 返回文件数用于分页
            "total_matches": total,  # 总匹配数（用于显示）
            "cached": cached is not None
        }

    @staticmethod
    def clear_cache(task_id: str):
        """清除指定任务的缓存"""
        for f in CACHE_DIR.glob(f"referer_cache_{task_id}_*"):
            try:
                f.unlink()
            except Exception:
                pass
