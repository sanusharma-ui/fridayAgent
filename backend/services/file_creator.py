"""Create user-requested files inside the temporary safe workspace."""

from pathlib import Path


class FileCreator:
    """Write new UTF-8 files while keeping every path under one directory."""

    def __init__(self, directory=r"D:\test"):
        self.directory = Path(directory)

    def create(self, filename, content):
        if not isinstance(filename, str) or not filename.strip():
            return "Please provide a filename."
        if not isinstance(content, str) or not content:
            return "Please provide file content."

        root = self.directory.resolve()
        candidate = (root / filename.strip()).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return r"For safety, files can only be created inside D:\test."

        if candidate == root or candidate.name in {".", ".."}:
            return "Please provide a valid filename."
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with candidate.open("x", encoding="utf-8", newline="") as file:
                file.write(content)
        except FileExistsError:
            return f"That file already exists: {candidate}"
        except (OSError, ValueError) as exc:
            return f"Could not create the file: {exc}"
        return f"File created: {candidate}"
