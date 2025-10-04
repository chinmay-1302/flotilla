import socket


def get_ip_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)  # 2 second timeout
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except (socket.timeout, OSError):
        # Fallback to localhost if network detection fails
        return "127.0.0.1"


def get_ip_address_docker() -> str:
    return socket.gethostbyname(socket.gethostname())
