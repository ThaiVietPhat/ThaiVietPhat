import os
import requests
import json
import re
import base64
from typing import Optional, List, Dict, Any, Tuple
from google import genai
from google.genai import types

class GitHubClient:
    def __init__(self, username: str, token: Optional[str] = None):
        self.username = username
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})

    def get(self, url: str) -> Optional[requests.Response]:
        try:
            response = self.session.get(url)
            if response.status_code == 404:
                return None
            if response.status_code == 403:
                print(f"API rate limit exceeded or access denied for {url}.")
                return None
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"API request failed for {url}: {e}")
            return None

    def get_repo_languages(self, repo_name: str) -> Dict[str, int]:
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        response = self.get(url)
        return response.json() if response else {}

    def get_file_content(self, repo_name: str, filepath: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{filepath}"
        response = self.get(url)
        if response:
            data = response.json()
            if isinstance(data, dict) and "content" in data:
                try:
                    return base64.b64decode(data["content"]).decode("utf-8")
                except Exception:
                    pass
        return None

    def check_path_exists(self, repo_name: str, filepath: str) -> bool:
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{filepath}"
        response = self.get(url)
        return response is not None

    def fetch_top_repositories(self) -> List[Dict[str, Any]]:
        print("Fetching top repositories...")
        url = f"https://api.github.com/users/{self.username}/repos?sort=updated&per_page=100"
        response = self.get(url)
        if not response:
            return []

        repos = response.json()
        top_repos = []
        for repo in repos:
            if (not repo.get("fork") and
                repo.get("name") != self.username and
                repo.get("description") and
                repo.get("stargazers_count", 0) > 0):
                 top_repos.append(repo)
        top_repos.sort(key=lambda x: (x['stargazers_count'], x['updated_at']), reverse=True)
        return top_repos[:3]

class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)

    def analyze_tech_stack(self, repo_name: str, description: str, files_content: Dict[str, str]) -> List[Tuple[str, str, str, str]]:
        # Truncate content dictionary safely instead of truncating the JSON string
        truncated_files = {}
        total_len = 0
        for path, content in files_content.items():
            if total_len > 10000:
                break
            truncated_files[path] = content[:2000]
            total_len += len(truncated_files[path])

        prompt = f"""
Analyze the provided repository details and file contents to extract the key technical stack.
Repository Name: {repo_name}
Description: {description}
Files Content:
{json.dumps(truncated_files, indent=2)}

Return a JSON array of objects representing the technical highlights. Each object must have the following keys:
- "name": The name of the technology (e.g., "Java 21", "Spring Boot", "PostgreSQL").
- "color": A hex color code without the '#' (e.g., "ED8B00" for Java).
- "logo": The corresponding simple-icons logo slug (e.g., "openjdk", "spring-boot", "postgresql").
- "description": A concise technical description of how it's used based on the provided context (e.g., "Primary DB with Flyway migrations").

Ensure the response strictly contains only valid JSON.
"""
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            result_json = json.loads(response.text)

            tech_stack = []
            for item in result_json:
                tech_stack.append((
                    item.get("name", "Unknown"),
                    item.get("color", "000000"),
                    item.get("logo", "github"),
                    item.get("description", "")
                ))
            return tech_stack

        except Exception as e:
            print(f"Error during Gemini analysis for {repo_name}: {e}")
            return []

class TechAnalyzer:
    def __init__(self, github_client: GitHubClient, gemini_client: Optional[GeminiClient] = None):
        self.github_client = github_client
        self.gemini_client = gemini_client

    def analyze_repo(self, repo: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
        repo_name = repo["name"]
        print(f"Analyzing {repo_name}...")
        description = repo.get("description", "") or ""

        if not self.gemini_client:
            print("Gemini API key not provided, skipping deep analysis.")
            return []

        # Gather key files
        files_to_check = [
            "README.md", "pom.xml", "package.json", "build.gradle",
            "Dockerfile", "docker-compose.yml",
            "application.yml", "application.properties",
            "src/main/resources/application.yml", "src/main/resources/application.properties"
        ]

        files_content = {}
        for filepath in files_to_check:
            content = self.github_client.get_file_content(repo_name, filepath)
            if content:
                # Keep only the first few KB of each file to avoid huge payloads
                files_content[filepath] = content[:2000]

        # Call Gemini Client
        return self.gemini_client.analyze_tech_stack(repo_name, description, files_content)

class MarkdownGenerator:
    def generate(self, repos: List[Dict[str, Any]], analyzer: TechAnalyzer) -> str:
        md_content = ""
        for repo in repos:
            tech_stack = analyzer.analyze_repo(repo)
            name = repo["name"].replace("-", " ").title()
            description = repo.get("description") or "No description provided."
            url = repo["html_url"]
            stars = repo['stargazers_count']

            # Modern Header
            md_content += f"### 💡 {name}\n\n"
            md_content += f"> **Status:** Active | **Stars:** ⭐ {stars}\n>\n"
            md_content += f"> {description}\n\n"

            if tech_stack:
                # Use Details/Summary for a cleaner look
                md_content += "<details>\n"
                md_content += "<summary><b>🛠️ Technical Highlights & Stack</b></summary>\n<br>\n\n"

                md_content += "<table>\n"
                md_content += "<tr>\n"
                md_content += "<th width=\"30%\">Technology</th>\n"
                md_content += "<th width=\"70%\">Implementation Details</th>\n"
                md_content += "</tr>\n"

                for tech_name, color, logo, tech_desc in tech_stack:
                    encoded_name = tech_name.replace(" ", "_").replace("-", "_")
                    badge = f"<img src=\"https://img.shields.io/badge/{encoded_name}-{color}?style=flat-square&logo={logo}&logoColor=white\" alt=\"{tech_name}\" />"
                    md_content += "<tr>\n"
                    md_content += f"<td align=\"center\">{badge}</td>\n"
                    md_content += f"<td>{tech_desc}</td>\n"
                    md_content += "</tr>\n"

                md_content += "</table>\n\n"
                md_content += "</details>\n\n"

            # Footer with Quick Links and Top Badges
            md_content += "<p>\n"
            md_content += f"  <a href=\"{url}\">\n"
            md_content += f"    <img src=\"https://img.shields.io/badge/Source_Code-View_on_GitHub-181717?style=for-the-badge&logo=github&logoColor=white\" />\n"
            md_content += "  </a>\n"

            if tech_stack:
                 for tech_name, color, logo, _ in tech_stack[:3]: # Limit to top 3 badges
                      encoded_name = tech_name.replace(" ", "_")
                      md_content += f"  <img src=\"https://img.shields.io/badge/{encoded_name}-{color}?style=for-the-badge&logo={logo}\" />\n"

            md_content += "</p>\n\n"
            md_content += "---\n\n"

        return md_content

class ReadmeUpdater:
    def __init__(self, filepath: str = "README.md"):
        self.filepath = filepath

    def update(self, md_content: str) -> None:
        try:
            with open(self.filepath, "r") as f:
                readme_data = f.read()

            start_marker = "<!-- START_FEATURED_PROJECTS -->"
            end_marker = "<!-- END_FEATURED_PROJECTS -->"

            start_idx = readme_data.find(start_marker)
            end_idx = readme_data.find(end_marker)

            if start_idx != -1 and end_idx != -1:
                new_readme = (
                    readme_data[:start_idx + len(start_marker)] + "\n\n" +
                    md_content + "\n" +
                    readme_data[end_idx:]
                )

                with open(self.filepath, "w") as f:
                    f.write(new_readme)
                print(f"Successfully updated {self.filepath}")
            else:
                print(f"Could not find start or end markers in {self.filepath}")
        except Exception as e:
            print(f"Error updating {self.filepath}: {e}")

if __name__ == "__main__":
    username = "ThaiVietPhat"
    token = os.environ.get("GITHUB_TOKEN")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")

    client = GitHubClient(username, token)

    gemini_client = None
    if gemini_api_key:
        gemini_client = GeminiClient(gemini_api_key)

    analyzer = TechAnalyzer(client, gemini_client)
    generator = MarkdownGenerator()
    updater = ReadmeUpdater()

    repos = client.fetch_top_repositories()
    if repos:
        md = generator.generate(repos, analyzer)
        updater.update(md)
    else:
        print("No repositories found to process.")
