import socket
import subprocess
import platform


def get_ip_address() -> str:
    """Get the local IP address using multiple fallback methods."""
    # Method 1: Try connecting to a local address first
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connect to a local address (doesn't actually send data)
            s.connect(("192.168.1.1", 80))
            return s.getsockname()[0]
    except:
        pass

    # Method 2: Try connecting to Google DNS with shorter timeout
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)  # Set shorter timeout
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        pass

    # Method 3: Use hostname resolution
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        pass

    # Method 4: Use system command (platform-specific)
    try:
        if platform.system() == "Darwin":  # macOS
            result = subprocess.run(
                ["ifconfig"], capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.split("\n")
            for line in lines:
                if "inet " in line and "127.0.0.1" not in line:
                    return line.split()[1]
        elif platform.system() == "Linux":
            result = subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip().split()[0]
    except:
        pass

    # Fallback: return localhost
    return "127.0.0.1"


def get_ip_address_docker() -> str:
    return socket.gethostbyname(socket.gethostname())
