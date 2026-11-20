"""Public source repositories, pinned to the commits every build has used.

Each is fetched shallowly at an exact commit into <label_root> (git-ignored data/
by default). A checkout at any other commit is refused rather than used. Large
repositories are fetched partially: only the listed paths are checked out (sparse
checkout) and only their file contents are downloaded (``--filter=blob:none``).

    smartbug-dataset        SmartBugs curated: Dataset A annotations
    SolidiFI-benchmark      SolidiFI injected bugs and BugLogs: Datasets A and B
    DASP-DAppSCAN-datasets  the MANDO-LLM authors' DAppSCAN release: Dataset B's
                            cleaned sources, line labels and SWC -> category mapping
    ge-sc                   the authors' earlier repository: the 2,742 SmartBugs Wild
                            contracts no SmartBugs tool flags (paper Sec. 5.1, item 4)
"""
import subprocess
from pathlib import Path

REPOSITORIES = {
    "smartbug-dataset": ("https://github.com/smartbugs/smartbugs-curated.git",
                         "230e649123477eff332742a59a1c7cc6dc286cab", None),
    "SolidiFI-benchmark": ("https://github.com/DependableSystemsLab/SolidiFI-benchmark.git",
                           "4b0573e1b3f7031396de6f48f7f3e7380222ad3a", None),
    "DASP-DAppSCAN-datasets": ("https://github.com/MANDO-Project/DASP-DAppSCAN-datasets.git",
                               "f6b91009bf1103147dcd24ab4f963618939e8be9",
                               ("DAppSCAN-source/cleaned_SWCsource", "DAppSCAN-source/DASP_cleaned_labels",
                                "DAppSCAN-source/dasp_categories")),
    "ge-sc": ("https://github.com/MANDO-Project/ge-sc.git",
              "c7b530358ddfef83aca43b7026833341541d788e", ("data/smartbugs-wild-clean-contracts",)),
}
DEFAULT = ("smartbug-dataset", "SolidiFI-benchmark")


def _git(directory, *args):
    result = subprocess.run(["git", "-C", str(directory)] + list(args), capture_output=True, text=True)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout,
                                            "%s\n%s" % (result.stderr.strip(), " ".join(result.args)))
    return result.stdout.strip()


def _fetch(directory, url, commit, partial):
    try:
        _git(directory, "fetch", "-q", "--depth", "1", *(["--filter=blob:none"] if partial else []),
             "origin", commit)
    except subprocess.CalledProcessError as error:
        raise SystemExit("Could not fetch %s at %s:\n%s\nCheck that this machine (and, in Docker, the "
                         "container) can reach GitHub; behind a proxy see docker/README.md."
                         % (url, commit, error.stderr)) from None


def head(directory):
    try:
        return _git(directory, "rev-parse", "HEAD")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _checked_out(directory, paths):
    return paths is None or all((Path(directory) / p).exists() for p in paths)


def ensure(label_root, names=DEFAULT):
    """Fetch any missing repository at its pinned commit; return {name: commit}."""
    label_root = Path(label_root)
    label_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        url, commit, paths = REPOSITORIES[name]
        directory = label_root / name
        if head(directory) == commit and _checked_out(directory, paths):
            continue
        if not (directory / ".git").is_dir():
            directory.mkdir(parents=True, exist_ok=True)
            _git(directory, "init", "-q")
            _git(directory, "remote", "add", "origin", url)
        if paths is not None:
            _git(directory, "sparse-checkout", "set", *paths)
        _fetch(directory, url, commit, partial=paths is not None)
        _git(directory, "checkout", "-q", "--detach", "FETCH_HEAD")
    return verify(label_root, names)


def verify(label_root, names=DEFAULT):
    """{name: commit} if every repository is at its pinned commit, else raise."""
    found = {}
    for name in names:
        _, commit, paths = REPOSITORIES[name]
        directory = Path(label_root) / name
        actual = head(directory)
        if actual != commit or not _checked_out(directory, paths):
            raise SystemExit("%s under %s is at %s, expected %s; run: python -m hcg fetch%s"
                             % (name, label_root, actual, commit,
                                "" if name in DEFAULT else " --dataset B"))
        found[name] = commit
    return found
