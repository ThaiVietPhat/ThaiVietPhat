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
            if response.status_code in (404, 403):
                if response.status_code == 403:
                    print(f"Rate limit or forbidden on {url}: {response.text}")
                return None
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
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

class TechAnalyzer:
    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY environment variable is not set. Tech analysis might fail.")
        self.ai_client = genai.Client(api_key=api_key)

    def analyze_repo(self, repo: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
        repo_name = repo["name"]
        print(f"Analyzing {repo_name} using Gemini...")

        # Gather context
        topics = repo.get("topics", [])
        description = repo.get("description", "") or ""
        languages = list(self.github_client.get_repo_languages(repo_name).keys())

        context_parts = [
            f"Repository Name: {repo_name}",
            f"Description: {description}",
            f"Topics: {', '.join(topics) if topics else 'None'}",
            f"Languages: {', '.join(languages) if languages else 'None'}",
        ]

        # Optionally gather snippets of key files
        files_to_check = ["pom.xml", "package.json", "build.gradle", "README.md", "docker-compose.yml", "Dockerfile"]
        for filepath in files_to_check:
            content = self.github_client.get_file_content(repo_name, filepath)
            if content:
                # Truncate content to avoid huge prompts
                truncated_content = content[:1500] + ("..." if len(content) > 1500 else "")
                context_parts.append(f"\n--- {filepath} (snippet) ---\n{truncated_content}")

        full_context = "\n".join(context_parts)

        prompt = f"""
You are an expert software architect. Analyze the provided repository context and identify the core technologies used.
For each core technology identified, output a JSON object with exactly the following string keys:
- "tech_name": The standard name of the technology (e.g., "Java", "Spring Boot", "Docker", "Apache Kafka").
- "color": A 6-character hex color code representing the technology's brand color (e.g., "ED8B00" for Java). Do NOT include the # symbol.
- "logo": The corresponding simpleicons slug/identifier for the technology logo (e.g., "openjdk", "spring-boot", "docker", "apache-kafka"). Use standard simpleicons naming.
- "tech_desc": A concise, highly specific, professional description of how this technology is likely used in THIS project based on the context. Max 1-2 short sentences. Do not use generic descriptions if specific context is available.

Return a JSON array of these objects representing the top 3-6 most important technologies.

Context:
{full_context}
"""

        try:
            response = self.ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )

            result_json = response.text
            tech_list = json.loads(result_json)

            tech_stack = []
            for item in tech_list:
                if all(k in item for k in ("tech_name", "color", "logo", "tech_desc")):
                    tech_stack.append((item["tech_name"], item["color"], item["logo"], item["tech_desc"]))

            return tech_stack

        except Exception as e:
            print(f"Error calling Gemini API for {repo_name}: {e}")
            return []

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

    client = GitHubClient(username, token)
    analyzer = TechAnalyzer(client)
    generator = MarkdownGenerator()
    updater = ReadmeUpdater()

    repos = client.fetch_top_repositories()
    if repos:
        md = generator.generate(repos, analyzer)
        updater.update(md)
    else:
        print("No repositories found to process.")
