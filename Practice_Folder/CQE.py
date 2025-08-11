import os
import shutil
import requests
import subprocess
import time
from urllib.parse import urlparse
import anthropic
import sqlite3
import json
import csv
import signal

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


    def clone_repo(self, clone_url, force_delete=False, max_retries=5):
        repo_name = clone_url.split("/")[-1].replace(".git", "")
        dest_path = os.path.join(self.local_dir, repo_name)

        def do_clone():
            print(f"Cloning repo into {dest_path}")
            # Capture output for error analysis
            result = subprocess.run(["git", "clone", clone_url, dest_path], check=True, capture_output=True, text=True)
            return result

        # Retry logic for transient errors (e.g., 503, GH100)
        attempt = 0
        delay = 5
        while True:
            try:
                if os.path.exists(dest_path):
                    if force_delete:
                        print(f"Deleting existing directory at {dest_path}")
                        shutil.rmtree(dest_path)
                        do_clone()
                    else:
                        print(f"Repository already exists at {dest_path}")
                else:
                    do_clone()
                break  # Success
            except subprocess.CalledProcessError as e:
                # Always try to decode stderr for error analysis
                err_output = ""
                if hasattr(e, 'stderr') and e.stderr:
                    if isinstance(e.stderr, bytes):
                        err_output = e.stderr.decode(errors='replace')
                    else:
                        err_output = str(e.stderr)
                elif hasattr(e, 'output') and e.output:
                    if isinstance(e.output, bytes):
                        err_output = e.output.decode(errors='replace')
                    else:
                        err_output = str(e.output)
                else:
                    err_output = str(e)
                # Check for transient errors
                is_transient = False
                if ("503" in err_output or "Service Unavailable" in err_output or
                    "GH100" in err_output or "The service is temporarily unavailable" in err_output):
                    is_transient = True
                if is_transient and attempt < max_retries:
                    print(f"Transient error during git clone (attempt {attempt+1}/{max_retries}): {err_output}\nRetrying in {delay} seconds...")
                    time.sleep(delay)
                    attempt += 1
                    delay = min(delay * 2, 120)
                    continue
                else:
                    print(f"git clone failed: {err_output}")
                    raise

        # --- Begin: Clean up tracked build artifacts and update .gitignore ---
        build_artifacts = [
            ".scannerwork",
            "build",
            "target",
            "out",
            "dist",
            "node_modules"
        ]
        gitignore_path = os.path.join(dest_path, ".gitignore")
        # Read or create .gitignore
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                gitignore_lines = f.read().splitlines()
        else:
            gitignore_lines = []
        # Add build artifacts to .gitignore if not present
        updated = False
        for artifact in build_artifacts:
            if artifact not in gitignore_lines:
                gitignore_lines.append(artifact)
                updated = True
        if updated:
            with open(gitignore_path, "w") as f:
                f.write("\n".join(gitignore_lines) + "\n")
            print("Updated .gitignore with build artifacts.")
        # Remove build artifacts from git tracking if present
        for artifact in build_artifacts:
            artifact_path = os.path.join(dest_path, artifact)
            if os.path.exists(artifact_path):
                # Only try to untrack if it's tracked
                result = subprocess.run(["git", "ls-files", "--error-unmatch", artifact], cwd=dest_path, capture_output=True)
                if result.returncode == 0:
                    subprocess.run(["git", "rm", "-r", "--cached", artifact], cwd=dest_path, check=False)
                    print(f"Removed {artifact} from git tracking.")
        # Stage .gitignore changes (but do not commit here)
        subprocess.run(["git", "add", ".gitignore"], cwd=dest_path, check=False)
        # --- End: Clean up tracked build artifacts and update .gitignore ---

        return dest_path

    def download_local_version(self, repo_path):
        # Lists the downloaded files
        if not os.path.exists(repo_path):
            raise Exception(f"Path {repo_path} does not exist.")
        print(f"Local files in {repo_path}:")
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                print(file)

    def commit_and_push_changes(self, repo_path, commit_message="Apply automated changes"):
        print(f"Checking for changes in {repo_path}")
        original_cwd = os.getcwd()
        os.chdir(repo_path)

        try:
            # Remove .scannerwork from git tracking if present
            if os.path.isdir(os.path.join(repo_path, ".scannerwork")):
                subprocess.run(["git", "rm", "-r", "--cached", ".scannerwork"], check=False)

            # Stage all changes (including deletions and additions)
            subprocess.run(["git", "add", "-A"], check=True)

            # Check if there is anything to commit
            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
            if result.stdout.strip() == "":
                print("No changes to commit.")
                return

            # Commit
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            print("Changes committed.")

            # Get current branch name
            branch_result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True)
            current_branch = branch_result.stdout.strip()
            # Always pull before push to avoid non-fast-forward errors
            try:
                subprocess.run(["git", "pull", "origin", current_branch], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Warning: git pull failed: {e}")
            # Only push to the current branch, never create new branches or set upstream
            try:
                subprocess.run(["git", "push", "origin", current_branch], check=True)
                print(f"Pushed changes to origin/{current_branch}")
                return
            except subprocess.CalledProcessError as e:
                print(f"git push failed: {e}")
                raise

        finally:
            os.chdir(original_cwd)
            
class SonarCloudAnalyzer:
    def create_project(self, project_key, name, organization=None, visibility="public"):
        """
        Create a new project in SonarCloud using the API.
        Args:
            project_key (str): Unique key for the project (e.g., repo name).
            name (str): Display name for the project.
            organization (str, optional): SonarCloud organization key. Required for SonarCloud.
            visibility (str): 'public' or 'private'. Default is 'public'.
        """
        url = "https://sonarcloud.io/api/projects/create"
        data = {
            "project": project_key,
            "name": name,
            "visibility": visibility
        }
        if organization:
            data["organization"] = organization
        response = requests.post(url, headers=self.headers, data=data)
        if response.status_code == 200:
            print(f"Project '{name}' created successfully in SonarCloud.")
            print(f"Project details: {response.json()}")
            return response.json()
        elif response.status_code == 400 and "already exists" in response.text:
            print(f"Project '{name}' already exists in SonarCloud.")
            return None
        else:
            print(f"Failed to create project: {response.status_code} - {response.text}")
            raise Exception(f"SonarCloud project creation error: {response.status_code}")
    def __init__(self, sonar_token):
        self.sonar_token = sonar_token
        self.url = "https://sonarcloud.io/api/issues/search"
        self.headers = {"Authorization": f"Bearer {self.sonar_token}"}

    def analyze_repo(self, repo_name):
        parameters = {"componentKeys": repo_name}
        response = requests.get(self.url, headers=self.headers, params=parameters)
        if response.status_code == 200:
            print(f"Successfully fetched issues for {repo_name}.")
            print(f"Number of issues found: {len(response.json().get('issues', []))}")
            return response.json()
        else:
            print(f"Error fetching issues from SonarCloud: {response.status_code} - {response.text}")
            raise Exception(f"SonarCloud API error: {response.status_code}")

class IssueProcessor:
    def __init__(self, anthropic_api_key):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)

    def extract_code_block(self, text):
        """
        Extracts only the lines between the first and second triple backticks (```),
        excluding the backtick lines themselves. Removes common AI preambles (e.g., 'Here is the fixed code with the changes:').
        If no code block is found, returns the original text.
        """
        lines = text.splitlines()
        code_started = False
        code_lines = []
        for line in lines:
            if not code_started:
                if line.strip().startswith("```"):
                    code_started = True
                    continue  # skip the opening backticks (and possible language)
            elif code_started:
                if line.strip().startswith("```"):
                    break  # end of code block
                code_lines.append(line)
        # Remove common AI preambles from the start of the code block
        import re
        # More robust: match any line that starts with 'here', 'here is', 'here's', etc.,
        # followed by any combination of 'fixed', 'updated', 'entire', 'code', 'code file', 'file', 'with the changes', etc.
        preamble_regex = re.compile(
            r"^(here(('|’)s)?(\s+is)?(\s+the)?(\s+entire)?(\s+fixed)?(\s+updated)?(\s+code)?(\s+file)?(\s+code\s+file)?(\s+with\s+the\s+changes)?\s*[:\.]?\s*)$",
            re.IGNORECASE
        )
        while code_lines:
            first_line = code_lines[0].strip()
            # Remove punctuation for matching
            first_line_clean = re.sub(r'[^a-zA-Z ]', '', first_line).strip()
            if preamble_regex.match(first_line) or preamble_regex.match(first_line_clean):
                code_lines.pop(0)
            else:
                break
        if code_started and code_lines:
            return "\n".join(code_lines).strip("\n")
        return text.strip()

    def process_issue(self, issue, file_path):
        with open(file_path, "r") as input_file:
            input_text = input_file.read()

        prompt = (
            f"{issue['message']}. Here is an issue with some code. Write changes that can be made to the code to fix it. "
            "Please write the entire code file with all of its changes as a response. Do not add any reasoning or description, only the code. "
            "If there are any comments in the code, do not remove them. Do not explain why there is an issue, or state anything, just provide the fixed code."
        )

        retries = 0
        delay = 5
        while True:
            try:
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",  # Use Claude 3 Haiku model (widest availability)
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": f"{prompt}\n\n{input_text}"}
                    ]
                )
                # The response content is a list of message blocks; join them if needed
                if hasattr(response, 'content'):
                    if isinstance(response.content, list):
                        ai_output = "".join([block.text if hasattr(block, 'text') else str(block) for block in response.content])
                    else:
                        ai_output = str(response.content)
                else:
                    ai_output = str(response)
                return self.extract_code_block(ai_output)
            except anthropic.NotFoundError as e:
                print("Model not found. Please check your Anthropic dashboard and API key permissions. Error details:")
                print(e)
                raise
            except Exception as e:
                print(f"Error: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
                delay = min(delay * 2, 120)  # Exponential backoff with max delay of 2 minutes
                
class DatabaseManager:
    def export_issues_to_csv(self, csv_path="issues_export.csv"):

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM issues")
        rows = c.fetchall()
        headers = [description[0] for description in c.description]
        with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows(rows)
        conn.close()
        print(f"Exported {len(rows)} issues to {csv_path}")
    def __init__(self, db_path):
        self.db_path = db_path
        self.initialize_db()

    def initialize_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id TEXT PRIMARY KEY,
                rule TEXT,
                severity TEXT,
                component TEXT,
                project TEXT,
                hash TEXT,
                message TEXT,
                resolution TEXT,
                status TEXT,
                effort TEXT,
                debt TEXT,
                author TEXT,
                creationDate TEXT,
                updateDate TEXT,
                closeDate TEXT,
                type TEXT,
                organization TEXT,
                cleanCodeAttribute TEXT,
                cleanCodeAttributeCategory TEXT,
                tags TEXT,
                impacts TEXT
            )
        """)
        conn.commit()
        conn.close()

    def issue_exists(self, issue_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT 1 FROM issues WHERE id = ?", (issue_id,))
        exists = c.fetchone() is not None
        conn.close()
        return exists

    def insert_issue(self, issue_data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        try:
            c.execute("""
                INSERT INTO issues (
                    id, rule, severity, component, project, hash,
                    message, resolution, status, effort, debt,
                    author, creationDate, updateDate, closeDate,
                    type, organization, cleanCodeAttribute,
                    cleanCodeAttributeCategory, tags, impacts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                issue_data['key'],
                issue_data.get('rule'),
                issue_data.get('severity'),
                issue_data.get('component'),
                issue_data.get('project'),
                issue_data.get('hash'),
                issue_data.get('message'),
                issue_data.get('resolution'),
                issue_data.get('status'),
                issue_data.get('effort'),
                issue_data.get('debt'),
                issue_data.get('author'),
                issue_data.get('creationDate'),
                issue_data.get('updateDate'),
                issue_data.get('closeDate'),
                issue_data.get('type'),
                issue_data.get('organization'),
                issue_data.get('cleanCodeAttribute'),
                issue_data.get('cleanCodeAttributeCategory'),
                json.dumps(issue_data.get('tags', [])),
                json.dumps(issue_data.get('impacts', []))
            ))
            conn.commit()
            print(f"Issue {issue_data['key']} added.")
        except sqlite3.IntegrityError:
            print(f"Issue {issue_data['key']} already exists. Skipping.")
        finally:
            conn.close()
            
def get_env_or_prompt(env_var_name, prompt_message):
    """Get environment variable or prompt user for input if it doesn't exist."""
    value = os.getenv(env_var_name)
    if value:
        print(f"✓ {env_var_name} found in environment variables")
        return value
    else:
        print(f"✗ {env_var_name} not found in environment variables")
        return input(f"{prompt_message}: ")


def main():
    # TOGGLE: Set to True for full build check, False for syntax check only
    USE_BUILD_CHECK = True
    GITHUB_TOKEN = get_env_or_prompt("GITHUB_TOKEN", "Enter your GitHub token")
    SONAR_TOKEN = get_env_or_prompt("SONAR_TOKEN", "Enter your SonarQube token")
    ANTHROPIC_API_KEY = get_env_or_prompt("ANTHROPIC_API_KEY", "Enter your Anthropic API key")
    LOCAL_DIR = os.environ['TMPDIR'] + "CQE"
    REPO_URL =  input("Enter the GitHub repository URL: ")
    MAX_ITERATIONS = 30
    ISSUE_THRESHOLD = 10
    DB_PATH = "issues.db"
    ORGANIZATION = "jayak-patel"  # SonarCloud organization key (change as needed)

    
    github_manager = GitHubRepoManager(GITHUB_TOKEN, LOCAL_DIR)
    sonar_analyzer = SonarCloudAnalyzer(SONAR_TOKEN)
    issue_processor = IssueProcessor(ANTHROPIC_API_KEY)
    db_manager = DatabaseManager(DB_PATH)

    # --- Signal handler to export issues.db on forced stop ---
    def export_on_exit(signum, frame):
        print(f"\n[Signal] Received signal {signum}. Exporting issues to CSV before exit...", flush=True)
        try:
            db_manager.export_issues_to_csv("issues_export.csv")
        except Exception as e:
            print(f"[Error] Failed to export issues: {e}", flush=True)
        finally:
            exit(0)
    signal.signal(signal.SIGINT, export_on_exit)
    signal.signal(signal.SIGTERM, export_on_exit)


    # Fork and clone the repository
    forked_clone_url = github_manager.fork_repo(REPO_URL)
    local_path = github_manager.clone_repo(forked_clone_url, force_delete=True)

    # Parse repo name from URL
    parsed = urlparse(REPO_URL)
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) != 2:
        raise ValueError("Invalid GitHub repository URL format.")
    owner, repo = path_parts
    project_key = f"Jayak_Patel_{repo}"


    # Create SonarCloud project (if not exists)
    sonar_analyzer.create_project(project_key, repo, organization=ORGANIZATION, visibility="private")

    # Detect if Java files exist
    print("[Stage] Scanning for Java files ...", flush=True)
    t0 = time.time()
    java_files = []
    for root, dirs, files in os.walk(local_path):
        for file in files:
            if file.endswith('.java'):
                java_files.append(os.path.join(root, file))
    print(f"[Done] Found {len(java_files)} Java files in {time.time() - t0:.2f}s.", flush=True)

    sonar_binaries = []
    if java_files:
        print("[Stage] Java files detected. Attempting to build project for SonarCloud analysis...", flush=True)
        t0 = time.time()
        gradle_build_file = os.path.join(local_path, 'build.gradle')
        maven_build_file = os.path.join(local_path, 'pom.xml')
        gradle_wrapper = os.path.join(local_path, 'gradlew')
        maven_wrapper = os.path.join(local_path, 'mvnw')
        build_success = False

        def find_all_binaries(root, patterns):
            matches = []
            for dirpath, dirnames, filenames in os.walk(root):
                for pattern in patterns:
                    candidate = os.path.join(dirpath, *pattern)
                    if os.path.isdir(candidate):
                        matches.append(candidate)
            return matches

        if os.path.exists(gradle_build_file):
            gradle_cmds = []
            if os.path.exists(gradle_wrapper):
                gradle_cmds.append(["./gradlew", "build"])
            gradle_cmds.append(["gradle", "build"])
            for cmd in gradle_cmds:
                try:
                    subprocess.run(cmd, cwd=local_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    build_success = True
                    print(f"[Done] Gradle build succeeded with: {' '.join(cmd)} in {time.time() - t0:.2f}s.", flush=True)
                    break
                except Exception:
                    pass
            gradle_patterns = [
                ["build", "classes", "java", "main"],
                ["build", "classes", "main"],
                ["build", "classes"]
            ]
            gradle_binaries = find_all_binaries(local_path, gradle_patterns)
            if gradle_binaries:
                sonar_binaries.extend(gradle_binaries)
        elif os.path.exists(maven_build_file):
            maven_cmds = []
            if os.path.exists(maven_wrapper):
                maven_cmds.append(["./mvnw", "clean", "compile"])
            maven_cmds.append(["mvn", "clean", "compile"])
            for cmd in maven_cmds:
                try:
                    subprocess.run(cmd, cwd=local_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    build_success = True
                    print(f"[Done] Maven build succeeded with: {' '.join(cmd)} in {time.time() - t0:.2f}s.", flush=True)
                    break
                except Exception:
                    pass
            maven_patterns = [["target", "classes"]]
            maven_binaries = find_all_binaries(local_path, maven_patterns)
            if maven_binaries:
                sonar_binaries.extend(maven_binaries)
        else:
            print("[Info] No supported Java build system (Gradle or Maven) found. Please build manually and set sonar.java.binaries.", flush=True)
        if not build_success:
            print("[Info] Java build failed or not found. SonarScanner will likely fail unless binaries are provided.", flush=True)
        # Only keep existing directories that end with 'classes' or a valid Java binary dir
        valid_binary_suffixes = (os.sep + "classes", os.sep + "classes" + os.sep, os.sep + "main", os.sep + "main" + os.sep)
        filtered_binaries = []
        for d in sonar_binaries:
            if os.path.isdir(d) and (d.endswith("classes") or d.endswith("classes" + os.sep) or d.endswith("main") or d.endswith("main" + os.sep)):
                filtered_binaries.append(d)
            else:
                print(f"[Warning] Skipping invalid sonar.java.binaries path: {d}", flush=True)
        sonar_binaries = filtered_binaries
        if not sonar_binaries:
            print("[Info] No valid sonar.java.binaries directories found. Not setting property.", flush=True)

    # Generate sonar-project.properties in the repo directory
    sonar_properties_path = os.path.join(local_path, "sonar-project.properties")
    with open(sonar_properties_path, "w") as sonar_prop:
        sonar_prop.write(f"""
sonar.projectKey={project_key}
sonar.organization={ORGANIZATION}
sonar.host.url=https://sonarcloud.io
sonar.token={SONAR_TOKEN}
sonar.sources=.
sonar.exclusions=**/node_modules/**,**/build/**,**/dist/**,**/out/**,**/.scannerwork/**,**/target/**,**/.git/**,**/.idea/**,**/.vscode/**,**/venv/**,**/__pycache__/**,**/.DS_Store,**/tmp/**,**/temp/**,**/var/**,**/System/**,**/Library/**,**/com.apple.*/**,**/Store/**,**/.*/**
""")
        # Only write sonar.java.binaries if there are valid directories
        if sonar_binaries:
            sonar_prop.write(f"sonar.java.binaries={','.join(sonar_binaries)}\n")
    print(f"[Stage] Created sonar-project.properties at {sonar_properties_path}", flush=True)

    # Run SonarScanner CLI in the repo directory
    print("[Stage] Running SonarScanner CLI...", flush=True)
    try:
        result = subprocess.run(["sonar-scanner"], cwd=local_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print("[Done] SonarScanner CLI completed.", flush=True)
    except FileNotFoundError:
        print("[Error] sonar-scanner CLI not found. Please install SonarScanner CLI and ensure it is in your PATH.", flush=True)
        return
    except subprocess.CalledProcessError as e:
        print(f"[Error] SonarScanner CLI failed: {e}", flush=True)
        if e.stderr:
            print("[SonarScanner stderr output]:\n" + e.stderr, flush=True)
        return

    # Wait for SonarCloud analysis to complete (exponential backoff)
    delay = 5
    max_delay = 120
    analysis_complete = False
    while not analysis_complete:
        try:
            analysis_results = sonar_analyzer.analyze_repo(project_key)
            issues = analysis_results.get('issues', [])
            if len(issues) > 0:
                print(f"[Done] Analysis complete: issues found ({len(issues)})", flush=True)
                break
            ce_url = f"https://sonarcloud.io/api/ce/component"
            params = {"component": project_key}
            ce_response = requests.get(ce_url, headers=sonar_analyzer.headers, params=params)
            if ce_response.status_code == 200:
                ce_data = ce_response.json()
                queue = ce_data.get('queue', [])
                current = ce_data.get('current', {})
                if current and current.get('status') == 'SUCCESS':
                    print("[Done] SonarCloud analysis completed successfully.", flush=True)
                    break
                elif current and current.get('status') == 'FAILED':
                    print("[Error] SonarCloud analysis failed.", flush=True)
                    break
                else:
                    print(f"[Stage] Analysis in progress (status: {current.get('status', 'UNKNOWN')}). Waiting {delay} seconds...", flush=True)
            else:
                print(f"[Error] Error checking analysis status: {ce_response.status_code} - {ce_response.text}", flush=True)
        except Exception as e:
            print(f"[Error] Waiting for SonarCloud analysis to complete: {e}", flush=True)
        time.sleep(delay)
        delay = min(delay * 2, max_delay)


    def wait_for_sonarcloud_analysis(project_key, sonar_analyzer, max_delay=120):
        delay = 5
        while True:
            try:
                ce_url = f"https://sonarcloud.io/api/ce/component"
                params = {"component": project_key}
                ce_response = requests.get(ce_url, headers=sonar_analyzer.headers, params=params)
                if ce_response.status_code == 200:
                    ce_data = ce_response.json()
                    current = ce_data.get('current', {})
                    if current and current.get('status') == 'SUCCESS':
                        print("SonarCloud analysis completed successfully.")
                        break
                    elif current and current.get('status') == 'FAILED':
                        print("SonarCloud analysis failed.")
                        break
                    else:
                        print(f"Analysis in progress (status: {current.get('status', 'UNKNOWN')}). Waiting {delay} seconds...")
                else:
                    print(f"Error checking analysis status: {ce_response.status_code} - {ce_response.text}")
            except Exception as e:
                print(f"Waiting for SonarCloud analysis to complete: {e}")
            time.sleep(delay)
            delay = min(delay * 2, max_delay)

    IGNORE_ALREADY_FIXED_ISSUES = True  # Set to True to retry fixing all issues, even those already in DB

    for iteration in range(MAX_ITERATIONS):
        # Run SonarCloud analysis
        analysis_results = sonar_analyzer.analyze_repo(project_key)
        issues = analysis_results.get('issues', [])

        # Check if there are any new issues in the first 100
        def has_new_issues(issues, db_manager, limit=100):
            count = 0
            for issue in issues:
                if count >= limit:
                    break
                if not db_manager.issue_exists(issue['key']):
                    return True
                count += 1
            return False

        if not IGNORE_ALREADY_FIXED_ISSUES:
            # If all first 100 issues are already in DB, wait and poll until a new one appears or timeout
            wait_time = 0
            max_wait = 600  # 10 minutes max
            poll_delay = 10
            while not has_new_issues(issues, db_manager, limit=100) and wait_time < max_wait:
                print(f"No new issues in the first 100. Waiting for SonarCloud to update...")
                time.sleep(poll_delay)
                wait_time += poll_delay
                analysis_results = sonar_analyzer.analyze_repo(project_key)
                issues = analysis_results.get('issues', [])
            if not has_new_issues(issues, db_manager, limit=100):
                print(f"Timeout waiting for new issues from SonarCloud. Continuing anyway.")

        # If there are no issues at all, or below threshold, stop
        if len(issues) <= ISSUE_THRESHOLD:
            print(f"Number of issues ({len(issues)}) is below or equal to the threshold ({ISSUE_THRESHOLD}). Stopping iterations.")
            break

        # Process issues and apply fixes in batches, grouping by file
        BATCH_SIZE = 5  # Reduce batch size for smaller pushes
        batch_issues = []
        for issue in issues:
            if IGNORE_ALREADY_FIXED_ISSUES or not db_manager.issue_exists(issue['key']):
                batch_issues.append(issue)
            if len(batch_issues) >= BATCH_SIZE:
                # Group issues by file
                file_to_issues = {}
                for batch_issue in batch_issues:
                    file_path = os.path.join(local_path, batch_issue['component'].split(':')[-1])
                    if os.path.exists(file_path):
                        file_to_issues.setdefault(file_path, []).append(batch_issue)
                # For each file, apply all fixes in order, with safety check
                for file_path, issues_for_file in file_to_issues.items():
                    with open(file_path, "r") as f:
                        original_content = f.read()
                    file_content = original_content
                    for issue in issues_for_file:
                        file_content = issue_processor.process_issue(issue, file_path)
                    with open(file_path, "w") as f:
                        f.write(file_content)
                    # Check if file was actually changed by git
                    rel_file_path = os.path.relpath(file_path, local_path)
                    git_status = subprocess.run(["git", "status", "--porcelain", rel_file_path], cwd=local_path, capture_output=True, text=True)
                    file_changed = bool(git_status.stdout.strip())
                    if not file_changed:
                        print(f"No change detected in {file_path}, skipping build/syntax check.")
                        continue
                    # SAFETY CHECK: Build or Syntax
                    build_success = True
                    if USE_BUILD_CHECK:
                        gradle_build_file = os.path.join(local_path, 'build.gradle')
                        maven_build_file = os.path.join(local_path, 'pom.xml')
                        gradle_wrapper = os.path.join(local_path, 'gradlew')
                        maven_wrapper = os.path.join(local_path, 'mvnw')
                        build_cmd = None
                        if os.path.exists(gradle_build_file):
                            if os.path.exists(gradle_wrapper):
                                build_cmd = ["./gradlew", "build"]
                            else:
                                build_cmd = ["gradle", "build"]
                        elif os.path.exists(maven_build_file):
                            if os.path.exists(maven_wrapper):
                                build_cmd = ["./mvnw", "clean", "compile"]
                            else:
                                build_cmd = ["mvn", "clean", "compile"]
                        if build_cmd:
                            try:
                                subprocess.run(build_cmd, cwd=local_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            except subprocess.CalledProcessError as e:
                                print(f"Build failed after AI fix for {file_path}, reverting changes.")
                                with open(file_path, "w") as f:
                                    f.write(original_content)
                                build_success = False
                        if not build_success:
                            print(f"Reverted {file_path} to previous state due to failed build.")
                    else:
                        # Syntax check: javac for Java files
                        if file_path.endswith('.java'):
                            try:
                                subprocess.run(["javac", file_path], cwd=local_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            except subprocess.CalledProcessError as e:
                                print(f"Syntax check failed after AI fix for {file_path}, reverting changes.")
                                with open(file_path, "w") as f:
                                    f.write(original_content)
                                build_success = False
                            if not build_success:
                                print(f"Reverted {file_path} to previous state due to failed syntax check.")
                github_manager.commit_and_push_changes(local_path, f"Fix batch of {len(batch_issues)} issues")
                for batch_issue in batch_issues:
                    db_manager.insert_issue(batch_issue)
                batch_issues = []
                # Force SonarCloud analysis by running SonarScanner CLI again
                print("Forcing SonarCloud analysis by running SonarScanner CLI...")
                try:
                    result = subprocess.run(["sonar-scanner"], cwd=local_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    print("[Done] SonarScanner CLI completed.", flush=True)
                except FileNotFoundError:
                    print("sonar-scanner CLI not found. Please install SonarScanner CLI and ensure it is in your PATH.")
                    return
                except subprocess.CalledProcessError as e:
                    print(f"SonarScanner CLI failed: {e}")
                    if e.stderr:
                        print("[SonarScanner stderr output]:\n" + e.stderr, flush=True)
                    return
                # Wait for SonarCloud analysis to complete after push
                wait_for_sonarcloud_analysis(project_key, sonar_analyzer)
        # Commit and push any remaining files in the last batch
        if batch_issues:
            file_to_issues = {}
            for batch_issue in batch_issues:
                file_path = os.path.join(local_path, batch_issue['component'].split(':')[-1])
                if os.path.exists(file_path):
                    file_to_issues.setdefault(file_path, []).append(batch_issue)
            for file_path, issues_for_file in file_to_issues.items():
                with open(file_path, "r") as f:
                    file_content = f.read()
                for issue in issues_for_file:
                    file_content = issue_processor.process_issue(issue, file_path)
                with open(file_path, "w") as f:
                    f.write(file_content)
            github_manager.commit_and_push_changes(local_path, f"Fix batch of {len(batch_issues)} issues (final batch)")
            for batch_issue in batch_issues:
                db_manager.insert_issue(batch_issue)
            # Force SonarCloud analysis by running SonarScanner CLI again
            print("Forcing SonarCloud analysis by running SonarScanner CLI...")
            try:
                result = subprocess.run(["sonar-scanner"], cwd=local_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                print("[Done] SonarScanner CLI completed.", flush=True)
            except FileNotFoundError:
                print("sonar-scanner CLI not found. Please install SonarScanner CLI and ensure it is in your PATH.")
                return
            except subprocess.CalledProcessError as e:
                print(f"SonarScanner CLI failed: {e}")
                if e.stderr:
                    print("[SonarScanner stderr output]:\n" + e.stderr, flush=True)
                return
            # Wait for SonarCloud analysis to complete after final push
            wait_for_sonarcloud_analysis(project_key, sonar_analyzer)

    print(f"Process completed. New repository URL: {forked_clone_url}")
    # Export issues to CSV at the end
    db_manager.export_issues_to_csv("issues_export.csv")


if __name__ == "__main__":
    main()