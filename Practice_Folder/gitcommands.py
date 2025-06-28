import os
import subprocess
import requests
from urllib.parse import urlparse

class GitHubRepoManager:
    def __init__(self, github_token, local_dir):
        self.github_token = github_token
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.local_dir = local_dir
        os.makedirs(local_dir, exist_ok=True)

    def fork_repo(self, repo_url):
        """
        Fork a GitHub repo using the GitHub API.
        """
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) != 2:
            raise ValueError("Invalid GitHub repository URL format.")
        
        owner, repo = path_parts
        api_url = f"https://api.github.com/repos/{owner}/{repo}/forks"

        print(f"Forking repo: {owner}/{repo}")
        response = requests.post(api_url, headers=self.headers)
        if response.status_code == 202:
            print("Successfully forked the repository.")
            fork_data = response.json()
            return fork_data['clone_url']
        else:
            print(f"Failed to fork repo: {response.status_code} - {response.text}")
            raise Exception("Forking failed.")

    def clone_repo(self, clone_url):
        """
        Clone the repo using git.
        """
        repo_name = clone_url.split("/")[-1].replace(".git", "")
        dest_path = os.path.join(self.local_dir, repo_name)

        if os.path.exists(dest_path):
            print(f"Repository already exists at {dest_path}")
        else:
            print(f"Cloning repo into {dest_path}")
            subprocess.run(["git", "clone", clone_url, dest_path], check=True)

        return dest_path

    def download_local_version(self, repo_path):
        """
        List files in the local repository (as a proxy for 'downloading' content).
        """
        if not os.path.exists(repo_path):
            raise Exception(f"Path {repo_path} does not exist.")
        print(f"Local files in {repo_path}:")
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                print(os.path.relpath(os.path.join(root, file), repo_path))

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    GITHUB_TOKEN = "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"
    LOCAL_DIR = "./downloaded_repos"
    REPO_URL = "https://github.com/spring-projects/spring-integration-samples"

    manager = GitHubRepoManager(GITHUB_TOKEN, LOCAL_DIR)

    try:
        forked_clone_url = manager.fork_repo(REPO_URL)
        local_path = manager.clone_repo(forked_clone_url)
        manager.download_local_version(local_path)
    except Exception as e:
        print("Some Error occured:", e)
