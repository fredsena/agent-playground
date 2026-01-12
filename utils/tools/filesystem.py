import os
import pathlib
from langchain_core.tools import tool
from ..console import console
import re

@tool(
    "list_files_in_dir",
    parse_docstring=True,
    description=(
        "List all files and folders in a specified directory. "
        "Can filter by file extensions and search recursively."
    ),
)
def list_files_in_dir(
    folder_path: str,
    extensions: list[str] = None,
    recursive: bool = False,
    show_hidden: bool = False
) -> str:
    """List files in a directory with optional filtering.

    Args:
        folder_path (str): The path to the folder to list.
        extensions (list[str]): Optional list of extensions to filter (e.g., [".md", ".txt"]).
        recursive (bool): Whether to search subdirectories. Defaults to False.
        show_hidden (bool): Whether to show hidden files. Defaults to False.

    Returns:
        str: Formatted list of files found, or error message.
    """
    console.print(f"📁 Listing files in '[cyan]{folder_path}[/cyan]'", style="info")
    
    path = pathlib.Path(folder_path).expanduser().resolve()
    
    if not path.exists():
        return f"Error: Directory does not exist: {path}"
    
    if not path.is_dir():
        return f"Error: Path is not a directory: {path}"
    
    try:
        items = []
        iterator = path.rglob("*") if recursive else path.iterdir()
        
        for item in sorted(iterator):
            # Skip hidden files if not requested
            if not show_hidden and item.name.startswith('.'):
                continue
            
            # Skip directories when listing files
            if item.is_dir():
                continue
            
            # Filter by extension if specified
            if extensions:
                if item.suffix.lower() not in [ext.lower() for ext in extensions]:
                    continue
            
            items.append(str(item))
        
        if not items:
            return f"No files found in {path}" + (f" with extensions {extensions}" if extensions else "")
        
        result = f"Found {len(items)} file(s) in {path}:\n\n"
        for item in items:
            result += f"  📄 {item}\n"
        
        return result
    
    except PermissionError:
        return f"Error: Permission denied accessing {path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool(
    "read_file_content",
    parse_docstring=True,
    description=(
        "Read the contents of a text file from disk. "
        "Automatically detects encoding and handles large files."
    ),
)
def read_file_content(
    file_path: str,
    max_chars: int = 5000
) -> str:
    """Read content from a file on disk.

    Args:
        file_path (str): The full path to the file to read.
        max_chars (int): Maximum number of characters to return. Defaults to 5000.

    Returns:
        str: The file contents (possibly truncated), or error message.
    """
    console.print(f"📄 Reading file: '[cyan]{file_path}[/cyan]'", style="info")
    
    path = pathlib.Path(file_path).expanduser().resolve()
    
    if not path.exists():
        return f"Error: File does not exist: {path}"
    
    if not path.is_file():
        return f"Error: Path is not a file: {path}"
    
    try:
        # Try UTF-8 first
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            return f"Error: Cannot read file encoding: {str(e)}"
    except Exception as e:
        return f"Error reading file: {str(e)}"
    
    if not content:
        return f"File is empty: {path}"
    
    # Truncate if too long
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... [truncated, showing first {max_chars} of {len(content)} characters]"
    
    return f"=== Content of {path.name} ===\n\n{content}"


@tool(
    "write_results_file",
    parse_docstring=True,
    description=(
        "Write content to a file on disk. Creates parent directories if needed. "
        "Use this to save summaries, results, or any output file."
    ),
)
def write_results_file(
    file_path: str,
    content: str,
    append: bool = False
) -> str:
    """Write content to a file on disk.

    Args:
        file_path (str): The path where the file should be created/written.
        content (str): The content to write to the file.
        append (bool): If True, append to existing file. Defaults to False.

    Returns:
        str: Success message with file path and size, or error message.
    """
    console.print(f"✍️  Writing to file: '[cyan]{file_path}[/cyan]'", style="info")
    
    path = pathlib.Path(file_path).expanduser().resolve()
    
    try:
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        
        file_size = path.stat().st_size
        action = "appended to" if append else "written to"
        
        return f"✅ Successfully {action} '{path}' ({file_size} bytes)"
    
    except PermissionError:
        return f"Error: Permission denied writing to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool(
    "find_files",
    parse_docstring=True,
    description=(
        "Search for files by name pattern (glob) across a directory tree. "
        "Returns full paths to matching files."
    ),
)
def find_files(
    pattern: str,
    search_dir: str = ".",
    recursive: bool = True
) -> str:
    """Find files by name pattern.

    Args:
        pattern (str): The file pattern to search for (e.g., "*.txt", "config.*", "README*").
        search_dir (str): Directory to search in. Defaults to current directory.
        recursive (bool): Whether to search subdirectories. Defaults to True.

    Returns:
        str: Comma-separated list of matching file paths, or message if none found.
    """
    console.print(f"🔍 Searching for '[cyan]{pattern}[/cyan]' in '[blue]{search_dir}[/blue]'", style="info")
    
    search_path = pathlib.Path(search_dir).expanduser().resolve()
    
    if not search_path.exists():
        return f"Error: Directory does not exist: {search_path}"
    
    if not search_path.is_dir():
        return f"Error: Path is not a directory: {search_path}"
    
    try:
        if recursive:
            matches = list(search_path.glob(f"**/{pattern}"))
        else:
            matches = list(search_path.glob(pattern))
        
        # Filter out directories
        matches = [m for m in matches if m.is_file()]
        
        if matches:
            file_paths = [str(m.resolve()) for m in matches]
            return f"Found {len(file_paths)} file(s):\n" + "\n".join(f"  📄 {p}" for p in file_paths)
        else:
            return f"No files found matching '{pattern}' in {search_path}"
    
    except Exception as e:
        return f"Error during search: {str(e)}"
    

# Define allowed directories for file operations
ALLOWED_DIRS = [
    pathlib.Path.home() / "documents",  # /home/user/documents on Linux, C:\Users\user\documents on Windows
    pathlib.Path.home() / "Downloads",
    pathlib.Path("/tmp"),               # /tmp on Linux
    pathlib.Path("C:\\Users\\user\\AppData\\Local\\Temp") if os.name == 'nt' else pathlib.Path("/tmp")  # Temp on Windows
]

def is_path_allowed(file_path: str) -> bool:
    """Check if a file path is within allowed directories."""
    try:
        resolved = pathlib.Path(file_path).expanduser().resolve()
        return any(str(resolved).startswith(str(allowed.resolve())) for allowed in ALLOWED_DIRS)
    except Exception:
        return False

@tool(
    "find_file",
    parse_docstring=True,
    description=(
        "Find files by name or pattern across a directory tree. "
        "Works on both Linux and Windows. Returns the full paths of matching files."
    ),
)
def find_file(
    filename: str, 
    search_dir: str = ".",
    recursive: bool = True
) -> str:
    """Find files by name or pattern in a directory.

    Args:
        filename (str): The file name or pattern to search for (e.g., "*.txt", "config.json").
        search_dir (str): The directory to search in. Defaults to current directory.
        recursive (bool): Whether to search subdirectories. Defaults to True.

    Returns:
        str: Comma-separated list of full paths to matching files, or "No files found" if empty.

    Raises:
        ValueError: If the search directory doesn't exist.
    """
    console.print(f"🔍 Searching for '[cyan]{filename}[/cyan]' in '[blue]{search_dir}[/blue]'", style="info")
    
    # Convert to pathlib.Path for cross-platform compatibility
    search_path = pathlib.Path(search_dir).expanduser().resolve()
    
    if not search_path.exists():
        raise ValueError(f"Directory does not exist: {search_path}")
    
    if not search_path.is_dir():
        raise ValueError(f"Path is not a directory: {search_path}")
    
    # Search for matching files
    try:
        if recursive:
            # Recursive search using glob
            matches = list(search_path.glob(f"**/{filename}"))
        else:
            # Non-recursive search
            matches = list(search_path.glob(filename))
        
        if matches:
            # Convert to absolute paths and return as comma-separated string
            file_paths = [str(m.resolve()) for m in matches]
            return ", ".join(file_paths)
        else:
            return f"No files found matching '{filename}' in {search_path}"
    
    except Exception as e:
        return f"Error during search: {str(e)}"

@tool(
    "read_file",
    parse_docstring=True,
    description=(
        "Read the contents of a text file. "
        "Works on both Linux and Windows. Automatically detects encoding."
    ),
)
def read_file(
    file_path: str,
    max_lines: int = None
) -> str:
    """Read the contents of a text file.

    Args:
        file_path (str): The full path to the file to read.
        max_lines (int): Maximum number of lines to return. None means read entire file.

    Returns:
        str: The contents of the file, or an error message if file cannot be read.

    Raises:
        ValueError: If the file doesn't exist or cannot be read.
    """
    console.print(f"📄 Reading file: '[cyan]{file_path}[/cyan]'", style="info")
    
    # Convert to pathlib.Path for cross-platform compatibility
    path = pathlib.Path(file_path).expanduser().resolve()
    
    if not path.exists():
        raise ValueError(f"File does not exist: {path}")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    
    try:
        # Try to read with UTF-8 first (most common)
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Fall back to system default encoding if UTF-8 fails
        try:
            with open(path, 'r', encoding='latin-1') as f:
                lines = f.readlines()
        except Exception as e:
            raise ValueError(f"Cannot read file with UTF-8 or latin-1 encoding: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")
    
    # Limit lines if specified
    if max_lines is not None:
        lines = lines[:max_lines]
    
    # Join and return content
    content = ''.join(lines)
    
    if not content:
        return f"File is empty: {path}"
    
    return content     

@tool(
    "write_file",
    parse_docstring=True,
    description=(
        "Write or create a text file with the given content. "
        "Works on both Linux and Windows. Creates parent directories if needed."
    ),
)
def write_file(
    file_path: str,
    content: str,
    append: bool = False
) -> str:
    """Write content to a text file.

    Args:
        file_path (str): The full path where the file should be written.
        content (str): The content to write to the file.
        append (bool): If True, append to existing file. If False, overwrite. Defaults to False.

    Returns:
        str: Success message with file path and size, or an error message.

    Raises:
        ValueError: If the file cannot be written.
    """
    console.print(f"✍️  Writing to file: '[cyan]{file_path}[/cyan]'", style="info")
    
    # Convert to pathlib.Path for cross-platform compatibility
    path = pathlib.Path(file_path).expanduser().resolve()
    
    try:
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write or append to file
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        
        # Get file size in bytes
        file_size = path.stat().st_size
        action = "appended to" if append else "written to"
        
        return f"✅ Content successfully {action} '{path}' ({file_size} bytes)"
    
    except PermissionError:
        raise ValueError(f"Permission denied: Cannot write to {path}")
    except IOError as e:
        raise ValueError(f"IO error while writing file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error writing file: {str(e)}")

@tool(
    "list_files",
    parse_docstring=True,
    description="List all files and folders in a specified directory."
)
def list_files(folder_path: str, show_hidden: bool = False) -> str:
    """List all files and folders in a specified directory.
    
    Args:
        folder_path (str): The path to the folder to list.
                          Can be relative or absolute path.
                          Works on both Linux and Windows.
        show_hidden (bool): Whether to show hidden files (default: False).
                           On Linux, hidden files start with a dot.
    
    Returns:
        str: A formatted string listing all files and folders with their types.
    
    Raises:
        FileNotFoundError: If the folder does not exist.
        NotADirectoryError: If the path is not a directory.
    """
    print("📁 Invoking list_files tool")
    
    # Convert to pathlib Path for cross-platform compatibility
    path = pathlib.Path(folder_path).expanduser().resolve()
    
    # Validate the path exists and is a directory
    if not path.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder_path}")
    
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {folder_path}")
    
    # List files and directories
    items = []
    try:
        for item in sorted(path.iterdir()):
            # Skip hidden files if show_hidden is False
            if not show_hidden and item.name.startswith('.'):
                continue
            
            # Determine if it's a file or directory
            item_type = "📁 [DIR]" if item.is_dir() else "📄 [FILE]"
            items.append(f"{item_type}  {item.name}")
    
    except PermissionError:
        raise PermissionError(f"Permission denied accessing folder: {folder_path}")
    
    if not items:
        return f"Folder is empty: {folder_path}"
    
    result = f"Contents of {path}:\n\n" + "\n".join(items)
    return result    


@tool(
    "create_folder",
    parse_docstring=True,
    description="Create a new folder at the specified path."
)
def create_folder(folder_path: str, create_parents: bool = True) -> str:
    """Create a new folder at the specified path.
    
    Args:
        folder_path (str): The path where the folder should be created.
                          Can be relative or absolute path.
                          Works on both Linux and Windows.
                          Supports ~ for home directory expansion.
        create_parents (bool): Whether to create parent directories if they don't exist.
                            Defaults to True. If False, will raise an error if parent
                            directories don't exist.
    
    Returns:
        str: A success message with the full path of the created or existing folder.
    
    Raises:
        PermissionError: If permission is denied to create the folder.
        OSError: If other OS-level errors occur.
    """
    print("📁 Invoking create_folder tool")
    
    # Convert to pathlib Path for cross-platform compatibility
    path = pathlib.Path(folder_path).expanduser().resolve()
    
    # Check if folder already exists
    if path.exists() and path.is_dir():
        return f"ℹ️ Folder already exists: {path}"
    
    # Check if path exists but is a file (not a directory)
    if path.exists() and not path.is_dir():
        raise IsADirectoryError(f"Path exists but is a file, not a directory: {path}")
    
    try:
        if create_parents:
            # Create the folder and any parent directories
            path.mkdir(parents=True, exist_ok=True)
            return f"✅ Folder created successfully: {path}"
        else:
            # Create only the final folder (parents must exist)
            path.mkdir(parents=False, exist_ok=True)
            return f"✅ Folder created successfully: {path}"
    
    except PermissionError:
        raise PermissionError(f"Permission denied creating folder: {folder_path}")
    except OSError as e:
        raise OSError(f"Failed to create folder: {str(e)}")

@tool(
    "search_text_patterns",
    parse_docstring=True,
    description=(
        "Search for text patterns (regex) within files or directories. "
        "Works on Linux and Windows. Returns matching lines with file paths and line numbers."
    ),
)
def search_text_patterns(
    pattern: str, 
    path: str = ".",
    file_extension: str = "*",
    case_sensitive: bool = False,
    exclude_dirs: list[str] = None,
    max_depth: int = 10,
    max_files: int = 1000,
    max_results: int = 100
) -> str:
    """Search for text patterns within files using regex.
    
    Args:
        pattern (str): Regular expression pattern to search for.
        path (str): File or directory path to search in. Defaults to current directory.
        file_extension (str): File extension to filter by (e.g., '.py', '.txt'). 
                            Use '*' to search all files.
        case_sensitive (bool): Whether the search should be case-sensitive.
        exclude_dirs (list[str]): List of directory names to exclude from search.
                                 Defaults to common directories like .venv, .git, node_modules, etc.
        max_depth (int): Maximum directory depth to search. Defaults to 10.
        max_files (int): Maximum number of files to search. Defaults to 1000.
        max_results (int): Maximum number of results to return. Defaults to 100.
    
    Returns:
        str: Formatted results showing file paths, line numbers, and matching lines.
        
    Raises:
        ValueError: If the pattern is invalid regex or path doesn't exist.
    """
    console.print("🔍 Invoking search text patterns tool")
    
    # Default directories to exclude (common in most projects)
    default_exclude_dirs = {
        '.venv', 'venv', '.env', 'env',  # Python virtual environments
        '.git',  # Git directory
        'node_modules',  # Node.js dependencies
        '__pycache__', '.pytest_cache', '.mypy_cache',  # Python caches
        '.tox', '.nox',  # Python test runners
        'dist', 'build', '.eggs', '*.egg-info',  # Build artifacts
        '.idea', '.vscode',  # IDE settings
        'htmlcov', 'coverage',  # Coverage reports
    }
    
    # Use provided exclude_dirs or defaults
    if exclude_dirs is None:
        exclude_set = default_exclude_dirs
    else:
        exclude_set = set(exclude_dirs)
    
    try:
        # Compile regex pattern with case sensitivity option
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled_pattern = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")
    
    # Convert string path to pathlib.Path for cross-platform compatibility
    search_path = pathlib.Path(path).expanduser().resolve()
    
    if not search_path.exists():
        raise ValueError(f"Path does not exist: {path}")
    
    results = []
    files_searched = 0
    max_files_reached = False
    max_results_reached = False
    
    def should_exclude(file_path: pathlib.Path) -> bool:
        """Check if any part of the path is in the exclude set."""
        for part in file_path.parts:
            if part in exclude_set:
                return True
            # Also check for glob patterns like *.egg-info
            for excl_pattern in exclude_set:
                if '*' in excl_pattern and pathlib.PurePath(part).match(excl_pattern):
                    return True
        return False
    
    def get_depth(file_path: pathlib.Path, base_path: pathlib.Path) -> int:
        """Calculate directory depth relative to base path."""
        try:
            rel_path = file_path.relative_to(base_path)
            return len(rel_path.parts) - 1  # -1 because we don't count the file itself
        except ValueError:
            return 0
    
    # Determine if we're searching a directory or file
    if search_path.is_file():
        # Search single file
        try:
            with open(search_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    if compiled_pattern.search(line):
                        results.append(f"{search_path}:{line_num}: {line.rstrip()}")
                        if len(results) >= max_results:
                            max_results_reached = True
                            break
        except Exception as e:
            raise ValueError(f"Error reading file {search_path}: {e}")
    
    elif search_path.is_dir():
        # Search directory recursively
        # Build glob pattern based on file_extension
        glob_pattern = f"**/*{file_extension}" if file_extension != "*" else "**/*"
        
        for file_path in search_path.glob(glob_pattern):
            # Check if we've hit limits
            if max_results_reached or max_files_reached:
                break
            
            # Skip directories and hidden files
            if file_path.is_dir() or file_path.name.startswith('.'):
                continue
            
            # Skip excluded directories
            if should_exclude(file_path):
                continue
            
            # Check depth limit
            depth = get_depth(file_path, search_path)
            if depth > max_depth:
                continue
            
            # Check files limit
            files_searched += 1
            if files_searched > max_files:
                max_files_reached = True
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if compiled_pattern.search(line):
                            results.append(f"{file_path}:{line_num}: {line.rstrip()}")
                            if len(results) >= max_results:
                                max_results_reached = True
                                break
            except Exception:
                # Skip files that can't be read
                continue
    
    # Format output
    if not results:
        return f"No matches found for pattern '{pattern}' in {search_path} (searched {files_searched} files)"
    
    output = f"Found {len(results)} matches (searched {files_searched} files):\n\n"
    output += "\n".join(results)
    
    # Add limit warnings
    if max_files_reached:
        output += f"\n\n⚠️ Search stopped: reached max_files limit ({max_files}). Increase max_files to search more."
    if max_results_reached:
        output += f"\n\n⚠️ Search stopped: reached max_results limit ({max_results}). Increase max_results to see more."
    
    return output        