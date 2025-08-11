# Documentation: sonarCloud.py

## Overview

`CQE.py` is an automation script for running SonarCloud analysis, applying AI-powered code fixes, and managing issues for arbitrary GitHub repositories (with a focus on Java projects). It supports forking and cloning repos, running SonarCloud scans, applying code fixes using Anthropic Claude, committing and pushing changes, and exporting issue data to CSV.

---

## Main Features

- **GitHub Integration**: Forks and clones repositories using the GitHub API.
- **SonarCloud Integration**: Creates projects, runs analysis, and fetches issues from SonarCloud.
- **Java Build Detection**: Detects and builds Java projects using Gradle or Maven.
- **AI Code Fixes**: Uses Anthropic Claude to generate code fixes for SonarCloud issues, applying all fixes per file in memory before writing.
- **Batch Processing**: Applies and commits code fixes in small batches to avoid large git pushes.
- **.gitignore Management**: Automatically updates `.gitignore` and removes tracked build artifacts after cloning.
- **Database Management**: Tracks issues in a local SQLite database to avoid duplicate processing.
- **CSV Export**: Exports all issues from the database to a CSV file at the end of execution.

---

## Key Classes & Functions

### `GitHubRepoManager`
- `fork_repo(repo_url)`: Forks a GitHub repo and returns the clone URL.
- `clone_repo(clone_url, force_delete=False)`: Clones the repo, updates `.gitignore`, and removes tracked build artifacts.
- `commit_and_push_changes(repo_path, commit_message)`: Stages, commits, and pushes changes to the remote repo.

### `SonarCloudAnalyzer`
- `create_project(project_key, name, organization, visibility)`: Creates a new SonarCloud project.
- `analyze_repo(repo_name)`: Fetches issues for a given project from SonarCloud.

### `IssueProcessor`
- `process_issue(issue, file_path)`: Uses Anthropic Claude to generate a code fix for a given issue and file.
- `extract_code_block(text)`: Extracts the first code block from AI output, ignoring all other text.

### `DatabaseManager`
- `initialize_db()`: Creates the issues table if it doesn't exist.
- `issue_exists(issue_id)`: Checks if an issue is already in the database.
- `insert_issue(issue_data)`: Inserts a new issue into the database.
- `export_issues_to_csv(csv_path)`: Exports all issues to a CSV file.

---

## Workflow

1. **Setup**: Loads API keys and config from environment variables.
2. **Fork & Clone**: Forks and clones the target repo, cleans up tracked build artifacts.
3. **SonarCloud Project**: Creates a SonarCloud project if needed.
4. **Build Detection**: Detects and builds Java projects (Gradle/Maven).
5. **SonarCloud Analysis**: Runs SonarScanner and waits for analysis to complete.
6. **Iterative Fixing**:
   - Fetches issues from SonarCloud.
   - For each batch of new issues, applies AI code fixes grouped by file.
   - Commits and pushes changes, then waits for SonarCloud to update.
   - Repeats until the issue count drops below a threshold or max iterations reached.
7. **Export**: Exports all issues to `issues_export.csv` at the end.

---

## Environment Variables
- `GITHUB_TOKEN`: GitHub API token
- `SONAR_TOKEN`: SonarCloud API token
- `ANTHROPIC_API_KEY`: Anthropic Claude API key

---

## Variables to Change
- `ORGANIZATION` : SonarCloud Organization ID
- `BATCH` : Issues per commit
- `MAX_ITERATIONS` : Number of times that the code runs.

---

## Output Files
- `issues.db`: SQLite database of all processed issues
- `issues_export.csv`: CSV export of all issues

---

## Usage
Run the script as a standalone Python file:

```bash
python CQE.py
```

---

## Notes
- The script is designed for automation and may overwrite files in the cloned repo.
- Only the first code block from AI output is used for code fixes.
- The script is robust to SonarCloud analysis delays and will wait for new results before proceeding.
- All major steps and errors are logged to the console.

---


## Recent Improvements & Customization

- **Output Control**: All build and SonarScanner CLI output is suppressed unless there is an error. Only key progress and error messages are printed to the console.
- **SonarScanner Error Handling**: If SonarScanner fails, its stderr output is captured and printed for easier debugging.
- **Robust Binary Detection**: The script only writes `sonar.java.binaries` to the properties file if valid directories exist, preventing SonarScanner from failing due to missing paths.
- **Batch Processing**: Code fixes are applied and committed in small batches, with SonarCloud analysis forced after each batch.
- **Build/Syntax Check Skipping**: If no file changes are detected by git, build/syntax checks are skipped for efficiency.
- **.gitignore Management**: Automatically updates `.gitignore` and removes tracked build artifacts after cloning.
- **Stage/Timing Prints**: Major workflow stages and timing are printed for clarity, while verbose tool output is hidden.
- **AI Output Filtering**: Only the first code block from AI output is used for code fixes, with preambles removed.

---

## Authors
- Jayak Patel (and contributors)

---

For further customization or troubleshooting, see inline comments in the code.
