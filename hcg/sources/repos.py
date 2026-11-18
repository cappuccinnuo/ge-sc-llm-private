"""Public annotation repositories, pinned to the commits every build has used.

Both are fetched shallowly at an exact commit into <label_root> (git-ignored data/
by default). A checkout at any other commit is refused rather than used.
"""
import subprocess
from pathlib import Path

REPOSITORIES = {
    "smartbug-dataset": ("https://github.com/smartbugs/smartbugs-curated.git",
                         "230e649123477eff332742a59a1c7cc6dc286cab"),
    "SolidiFI-benchmark": ("https://github.com/DependableSystemsLab/SolidiFI-benchmark.git",
                           "4b0573e1b3f7031396de6f48f7f3e7380222ad3a"),
}


def _git(directory, *args):
    result = subprocess.run(["git", "-C", str(directory)] + list(args), capture_output=True, text=True)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout,
                                            "%s\n%s" % (result.stderr.strip(), " ".join(result.args)))
    return result.stdout.strip()


def _fetch(directory, url, commit):
    try:
        _git(directory, "fetch", "-q", "--depth", "1", "origin", commit)
    except subprocess.CalledProcessError as error:
        raise SystemExit("Could not fetch %s at %s:\n%s\nCheck that this machine (and, in Docker, the "
                         "container) can reach GitHub; behind a proxy see docker/README.md."
                         % (url, commit, error.stderr)) from None


def head(directory):
    try:
        return _git(directory, "rev-parse", "HEAD")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def ensure(label_root):
    """Fetch any missing repository at its pinned commit; return {name: commit}."""
    label_root = Path(label_root)
    label_root.mkdir(parents=True, exist_ok=True)
    for name, (url, commit) in REPOSITORIES.items():
        directory = label_root / name
        if head(directory) == commit:
            continue
        if not (directory / ".git").is_dir():
            directory.mkdir(parents=True, exist_ok=True)
            _git(directory, "init", "-q")
            _git(directory, "remote", "add", "origin", url)
        _fetch(directory, url, commit)
        _git(directory, "checkout", "-q", "--detach", "FETCH_HEAD")
    return verify(label_root)


def verify(label_root):
    """{name: commit} if every repository is at its pinned commit, else raise."""
    found = {}
    for name, (_, commit) in REPOSITORIES.items():
        actual = head(Path(label_root) / name)
        if actual != commit:
            raise SystemExit("%s under %s is at %s, expected %s; run: python -m hcg fetch"
                             % (name, label_root, actual, commit))
        found[name] = commit
    return found
