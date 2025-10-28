"""Runtime patches applied before application imports.

Currently used to provide backwards compatibility shims for third-party
packages whose APIs changed underneath pinned dependencies.
"""

from __future__ import annotations

import logging
import os
import shutil
import warnings
from typing import Any, Literal, cast

logger = logging.getLogger(__name__)


def _ensure_huggingface_cached_download() -> None:
    """Restore deprecated huggingface_hub.cached_download for sentence-transformers."""
    try:
        import huggingface_hub
        from huggingface_hub import hf_hub_download  # type: ignore
    except Exception:  # pragma: no cover - only executes when deps missing
        return

    if hasattr(huggingface_hub, "cached_download"):
        return

    def cached_download(  # type: ignore
        repo_id: str,
        filename: str,
        *,
        cache_dir: str | os.PathLike | None = None,
        force_download: bool = False,
        force_filename: str | None = None,
        resume_download: bool | None = None,
        proxies: dict | None = None,
        token: str | bool | None = None,
        use_auth_token: str | bool | None = None,
        revision: str | None = None,
        local_files_only: bool = False,
        legacy_cache_layout: bool = False,
        etag_timeout: float = 10,
        user_agent: dict | str | None = None,
        subfolder: str | None = None,
        repo_type: str | None = None,
        local_dir: str | os.PathLike | None = None,
        local_dir_use_symlinks: bool | str = "auto",
    ) -> str:
        """Compatibility wrapper routed to hf_hub_download."""
        if use_auth_token is not None and token is None:
            token = use_auth_token

        if proxies:
            warnings.warn(
                "Proxy configuration via cached_download shim is not supported; "
                "pass proxies via HF_HUB_* environment variables instead.",
                RuntimeWarning,
            )

        # Convert PathLike objects to strings for compatibility
        cache_dir_str = str(cache_dir) if cache_dir is not None else None
        local_dir_str = str(local_dir) if local_dir is not None else None
        
        # Handle local_dir_use_symlinks type conversion
        symlinks_param_raw = local_dir_use_symlinks
        if isinstance(symlinks_param_raw, str) and symlinks_param_raw != "auto":
            symlinks_param_raw = "auto"
        symlinks_param: bool | Literal["auto"] = cast(bool | Literal["auto"], symlinks_param_raw)

        # Call download with explicit kwargs; avoid passing unsupported params to satisfy type checkers
        path = cast(Any, hf_hub_download)(
            repo_id=repo_id,
            filename=filename,
            subfolder=subfolder,
            repo_type=repo_type,
            revision=revision,
            cache_dir=cache_dir_str,
            local_dir=local_dir_str,
            local_dir_use_symlinks=symlinks_param,
            user_agent=user_agent,
            force_download=force_download,
            proxies=proxies,
            etag_timeout=etag_timeout,
            token=token,
            local_files_only=local_files_only,
            resume_download=resume_download,
        )

        if force_filename and force_filename != os.path.basename(path):
            target_path = os.path.join(os.path.dirname(path), force_filename)
            if path != target_path:
                shutil.copy(path, target_path)
                path = target_path

        return path

    huggingface_hub.cached_download = cached_download  # type: ignore[attr-defined]
    try:
        all_names = getattr(huggingface_hub, "__all__")
    except AttributeError:
        pass
    else:
        if isinstance(all_names, list) and "cached_download" not in all_names:
            all_names.append("cached_download")
        elif isinstance(all_names, tuple) and "cached_download" not in all_names:
            # Replace tuple with list including the new symbol to match common __all__ usage
            huggingface_hub.__all__ = list(all_names) + ["cached_download"]  # type: ignore[attr-defined, assignment]

    logger.getChild("patches").info(
        "registered_cached_download_shim",
        extra={"shim": "huggingface_hub.cached_download"},
    )


_ensure_huggingface_cached_download()
