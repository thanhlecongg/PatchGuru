from abc import ABC, abstractmethod
from patchguru.utils.Logger import get_logger
from typing import Tuple, Optional

class Executor(ABC):
    """
    Abstract base class for executing Python code or files.
    Provides methods to execute Python files and code strings, capturing the output and errors.
    """

    def __init__(self):
        self.logger = get_logger("Executor")
        self.logger.debug("Executor initialized")

    @abstractmethod
    def execute_python_file(self, file_path: str, python_executable: str = "python3", timeout: Optional[int] = 30) -> Tuple[bool, str, str]:
        """
        Execute a Python file and return the result.

        Args:
            file_path: Path to the Python file to execute
            python_executable: Path to Python executable (default: "python3")
            timeout: Maximum execution time in seconds (default: 30)

        Returns:
            Tuple of (success: bool, stdout: str, stderr: str)
        """
        pass

    @abstractmethod
    def execute_python_code(self, code: str, python_executable: str = "python3", timeout: Optional[int] = 30) -> Tuple[bool, str, str]:
        """
        Execute Python code string and return the result.

        Args:
            code: Python code to execute
            python_executable: Path to Python executable (default: "python3")
            timeout: Maximum execution time in seconds (default: 30)

        Returns:
            Tuple of (success: bool, stdout: str, stderr: str)
        """
        pass
