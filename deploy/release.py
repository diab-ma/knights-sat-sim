"""Shared release validation; stdlib only, also installed root-owned on the host."""

import hashlib
import io
import json
import re
import urllib.error
import urllib.request
import zipfile

REPO = "senior-design-organization/knights-sat-sim"
REQUIRED = {
    "Python lint and tests", "TypeScript lint and tests",
    "Private hosting build and smoke checks", "Access JWT validator cases",
    "Publish revision images",
}
INPUTS = ("server/", "ui/", "deploy/Dockerfile", "deploy/nginx.conf",
          "compose.hosting.yml", ".dockerignore")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def revision(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value),
            "Select a full lowercase 40-character main commit SHA")
    return value


def fingerprint(tree):
    entries = sorted((item["path"], item["mode"], item["sha"]) for item in tree
                     if any(item["path"].startswith(p) if p.endswith("/")
                            else item["path"] == p for p in INPUTS)
                     and item["type"] != "tree")
    require(entries, "Missing bootstrap build inputs")
    return hashlib.sha256(json.dumps(entries).encode()).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def github(path, token):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as error:
        if error.code != 302:
            raise RuntimeError(f"GitHub request failed ({error.code}): {path}") from None
        # The artifact redirect is signed. Never send the GitHub token to its host.
        url = error.headers["Location"]
        require(url.startswith("https://"), "Unsafe artifact redirect")
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(1024 * 1024 + 1)
        require(len(data) <= 1024 * 1024, "Oversized release artifact")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("release.json")
            require(info.file_size < 16384, "Oversized release manifest")
            return json.loads(archive.read(info))


def select(sha, token, bootstrap):
    revision(sha)
    comparison = github(f"compare/{sha}...main", token)
    require(comparison["status"] in ("ahead", "identical"), "Revision is not on main")
    tree = github(f"git/trees/{sha}?recursive=1", token)
    require(not tree.get("truncated"), "Incomplete source tree")
    require(fingerprint(tree["tree"]) == bootstrap,
            "Bootstrap refuses changed application/build inputs; finish KSAT-25 admission integration")
    runs = github(f"actions/workflows/ci.yml/runs?head_sha={sha}&event=push&per_page=100", token)
    candidates = [r for r in runs["workflow_runs"]
                  if r["head_sha"] == sha and r["head_branch"] == "main"
                  and r["event"] == "push"]
    require(candidates, "No main push CI run for this revision")
    run = max(candidates, key=lambda r: r["id"])
    require(run["status"] == "completed" and run["conclusion"] == "success",
            "Latest exact-revision CI run has not passed")
    jobs = github(f"actions/runs/{run['id']}/jobs?per_page=100", token)
    require(jobs["total_count"] <= 100, "Too many CI jobs; update required-check validation")
    passed = {j["name"] for j in jobs["jobs"] if j["conclusion"] == "success"}
    require(REQUIRED <= passed, "Required CI checks are missing or failed")
    artifacts = github(f"actions/runs/{run['id']}/artifacts?per_page=100", token)
    matches = [a for a in artifacts["artifacts"]
               if a["name"] == f"release-{run['run_attempt']}" and not a["expired"]]
    require(len(matches) == 1, "Missing or ambiguous release artifact; rerun CI")
    release = github(f"actions/artifacts/{matches[0]['id']}/zip", token)
    require(release["revision"] == sha, "Artifact revision mismatch")
    for service in ("server", "web"):
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", release[service]), "Invalid image digest")
    release["run"] = run["html_url"]
    return release
