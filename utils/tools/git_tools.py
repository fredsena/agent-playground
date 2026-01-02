import subprocess
import os
import pathlib
from langchain.tools import tool

@tool(
    "git_command",
    parse_docstring=True,
    description=(
        "Execute Git commands for version control. "
        "Works on both Linux and Windows. "
        "Use for commits, pushes, pulls, status checks, and branch operations."
    ),
)
def git_command(
    command: str,
    repo_path: str = ".",
    include_output: bool = True
) -> str:
    """Execute a Git command in a repository.

    Args:
        command (str): The Git command to execute (e.g., "status", "add .", "commit -m 'message'").
                      Do NOT include "git" prefix, just the command and arguments.
        repo_path (str): Path to the Git repository. Defaults to current directory.
        include_output (bool): Include command output in result. Defaults to True.

    Returns:
        str: The output of the Git command or a success/error message.

    Raises:
        ValueError: If Git is not installed or command fails.
    """
    print(f"🔧 Git: {command}")
    
    repo_path = pathlib.Path(repo_path).expanduser().resolve()
    
    # Validate path
    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")
    
    if not (repo_path / ".git").exists():
        raise ValueError(f"Not a Git repository: {repo_path}")
    
    try:
        # Execute Git command
        result = subprocess.run(
            ["git", "-C", str(repo_path)] + command.split(),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            raise ValueError(f"Git error: {error_msg}")
        
        output = result.stdout.strip() if include_output else "✅ Command executed"
        return output if output else "✅ Git command completed"
    
    except subprocess.TimeoutExpired:
        raise ValueError("Git command timed out (30s)")
    except FileNotFoundError:
        raise ValueError("Git is not installed or not in PATH")
    except Exception as e:
        raise ValueError(f"Git command failed: {str(e)}")


@tool(
    "git_status",
    parse_docstring=True,
    description=("Check Git repository status including staged, unstaged, and untracked files."),
)
def git_status(repo_path: str = ".") -> str:
    """Get detailed Git repository status.

    Args:
        repo_path (str): Path to the Git repository. Defaults to current directory.

    Returns:
        str: Formatted Git status with branch, changes, and file information.
    """
    print(f"📊 Checking Git status in {repo_path}")
    
    repo_path = pathlib.Path(repo_path).expanduser().resolve()
    
    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True
        )
        branch = branch_result.stdout.strip()
        
        # Get status
        status_result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True,
            text=True
        )
        
        if not status_result.stdout.strip():
            return f"✅ Branch: {branch}\n🟢 Working directory is clean"
        
        # Parse status output
        staged = unstaged = untracked = 0
        for line in status_result.stdout.split("\n"):
            if line:
                status = line[:2]
                if status[0] == "?":
                    untracked += 1
                elif status[0] != " ":
                    staged += 1
                else:
                    unstaged += 1
        
        status_msg = f"📊 Branch: {branch}\n"
        if staged > 0:
            status_msg += f"✏️  Staged: {staged} file(s)\n"
        if unstaged > 0:
            status_msg += f"📝 Modified: {unstaged} file(s)\n"
        if untracked > 0:
            status_msg += f"❓ Untracked: {untracked} file(s)"
        
        return status_msg
    
    except Exception as e:
        raise ValueError(f"Failed to get Git status: {str(e)}")