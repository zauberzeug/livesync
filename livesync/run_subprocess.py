import subprocess


def run_subprocess(command: str, *, quiet: bool = False) -> None:
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        if not quiet:
            print(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        print(e.stdout.decode())
        raise
