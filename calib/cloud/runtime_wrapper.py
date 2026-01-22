from pathlib import Path


def wrap_command(command: list[str], shared_bin_dir: str, dont_wrap: bool = False, exe_name: str = "wrap") -> list[str]:
    """
    Wrap a command to run in a cloud environment with necessary setup.

    Args:
        command (List[str]): The original command to run.
        shared_bin_dir (str): The directory where the wrapper binary is located.
        dont_wrap (bool): If True, return the original command without wrapping.
        exe_name (str): The name of the wrapper executable.
    Returns:
        List[str]: The wrapped command.
    """
    if dont_wrap:
        return command

    command = " ".join(command)
    quoted_command = f"{Path(shared_bin_dir) / exe_name!s} run '{command}' --suffix \"$(JOB_NAME)/$(POD_NAME)_$(date +%Y%m%d_%H%M%S)\""
    return ["bash", "-c", quoted_command]


if __name__ == "__main__":
    # Example usage
    original_command = ["python", "script.py", "--arg1", "value1"]
    wrapped_command = wrap_command(original_command, shared_bin_dir="/shared/simulation/bin", dont_wrap=False, exe_name="wrap")
    print("Wrapped command:", wrapped_command)
