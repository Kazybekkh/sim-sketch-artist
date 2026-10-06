"""Fetch NVIDIA's versioned SO-101 USD assets; no previous application is used."""
from pathlib import Path
from urllib.request import urlopen

BASE = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Robots/RobotStudio/so101_new_calib/"
FILES = ["so101_new_calib.usd"] + [
    f"configuration/so101_new_calib_{part}.usd"
    for part in ("base", "physics", "robot", "sensor")
]


def fetch(destination=None):
    destination = Path(destination or Path(__file__).parent / "assets")
    for name in FILES:
        output = destination / name
        if output.is_file() and output.stat().st_size > 100:
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".downloading")
        with urlopen(BASE + name, timeout=90) as response:
            temporary.write_bytes(response.read())
        temporary.replace(output)
        print(f"Downloaded {output}", flush=True)
    return destination / FILES[0]


if __name__ == "__main__":
    fetch()
