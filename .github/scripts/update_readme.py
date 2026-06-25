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

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
        try:
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)
            response = self.session.get(url, headers=req_headers)
            if response.status_code == 404:
                return None
            if response.status_code == 403:
                print(f"API rate limit exceeded or forbidden for url: {url}")
                return None
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"API request failed for {url}: {e}")
            return None

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

    def get_file_content_raw(self, repo_name: str, filepath: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{filepath}"
        response = self.get(url, headers={"Accept": "application/vnd.github.v3.raw"})
        if response:
            return response.text
        return None

    def get_repo_languages(self, repo_name: str) -> Dict[str, int]:
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        response = self.get(url)
        return response.json() if response else {}

class TechAnalyzer:
    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
        api_key = os.environ.get("GEMINI_API_KEY")
        self.gemini_client = genai.Client(api_key=api_key) if api_key else None

    def generate_with_gemini(self, repo: Dict[str, Any], prompt: str) -> str:
        if not self.gemini_client:
             return "No API key"

        try:
             response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                     temperature=0.2,
                     max_output_tokens=1024
                )
             )
             return response.text
        except Exception as e:
             print(f"Error generating with Gemini: {e}")
             return ""

    def analyze_repo(self, repo: Dict[str, Any]) -> str:
        repo_name = repo["name"]
        print(f"Analyzing {repo_name}...")

        # Gather context
        readme_content = self.github_client.get_file_content_raw(repo_name, "README.md") or ""
        pom_content = self.github_client.get_file_content_raw(repo_name, "pom.xml") or ""
        pkg_content = self.github_client.get_file_content_raw(repo_name, "package.json") or ""

        languages = self.github_client.get_repo_languages(repo_name)

        context_parts = []
        if readme_content:
             # truncate to avoid token limits, 3000 chars should be plenty for overview
             context_parts.append(f"--- README.md ---\n{readme_content[:3000]}\n")
        if pom_content:
             context_parts.append(f"--- pom.xml ---\n{pom_content[:2000]}\n")
        if pkg_content:
             context_parts.append(f"--- package.json ---\n{pkg_content[:2000]}\n")

        context_parts.append(f"--- Top Languages ---\n{json.dumps(languages)}\n")

        full_context = "\n".join(context_parts)

        prompt = f"""
You are an expert developer summarizing a project for a GitHub Profile README.
I will provide you with files from a repository named "{repo_name}" (description: {repo.get('description', '')}).
Based on the provided context, extract the most prominent and special technical highlights and tech stack used.
You must output a highly detailed, professional, and elegant Markdown string representing the `<table>` and shield.io badges exactly like the example below. Do NOT include markdown code block formatting (like ```html), just output the raw HTML/Markdown string.

Here is an example format to follow EXACTLY for the table structure and shields:

<table>
<tr>
<th width="30%">Technology</th>
<th width="70%">Implementation Details</th>
</tr>
<tr>
<td align="center"><img src="https://img.shields.io/badge/Java_21-ED8B00?style=flat-square&logo=openjdk&logoColor=white" /></td>
<td>Java 21 with sealed interfaces, records, pattern matching</td>
</tr>
<tr>
<td align="center"><img src="https://img.shields.io/badge/Spring_Boot_4-6DB33F?style=flat-square&logo=spring-boot&logoColor=white" /></td>
<td>Spring Boot 4 + Spring Modulith — strict module boundary enforcement via Spring Events publication registry</td>
</tr>
<tr>
<td align="center"><img src="https://img.shields.io/badge/PostgreSQL-316192?style=flat-square&logo=postgresql&logoColor=white" /></td>
<td>Primary DB with Flyway migrations; Hibernate in validate mode</td>
</tr>
</table>

Instructions:
1. Identify 4-8 key technologies used in the project.
2. For each, generate a shield.io badge in the `<td align="center">...</td>`. Include the correct brand color and simple logos if possible (e.g. spring-boot, react, mysql, postgresql, redis, elasticsearch). Look at the example to see the shield structure. Use logoColor=white or logoColor=black as appropriate.
3. In the second `<td>`, provide 1 or 2 lines of very specific technical details based on the project context. Do not use generic statements like "Used for backend". Mention specific things like "Refresh token rotation with family tracking", or "WebRTC call signaling via STOMP relay" if found in the README context.
4. Output ONLY the `<table>...</table>` block.

Context files:
{full_context}
"""

        generated_table = self.generate_with_gemini(repo, prompt)

        # cleanup
        generated_table = generated_table.strip()
        if generated_table.startswith("```html"):
             generated_table = generated_table[7:]
        if generated_table.startswith("```"):
             generated_table = generated_table[3:]
        if generated_table.endswith("```"):
             generated_table = generated_table[:-3]

        return generated_table.strip()


class MarkdownGenerator:
    def generate(self, repos: List[Dict[str, Any]], analyzer: TechAnalyzer) -> str:
        md_content = ""
        for repo in repos:
            table_content = analyzer.analyze_repo(repo)
            name = repo["name"].replace("-", " ").title()
            description = repo.get("description") or "No description provided."
            url = repo["html_url"]
            stars = repo['stargazers_count']

            # Modern Header
            md_content += f"### 💡 {name}\n\n"
            md_content += f"> **Status:** Active | **Stars:** ⭐ {stars}\n>\n"
            md_content += f"> {description}\n\n"

            if table_content and table_content.startswith("<table"):
                md_content += "<details>\n"
                md_content += "<summary><b>🛠️ Technical Highlights & Stack</b></summary>\n<br>\n\n"
                md_content += table_content + "\n\n"
                md_content += "</details>\n\n"

            # Footer with Quick Links
            md_content += "<p>\n"
            md_content += f"  <a href=\"{url}\">\n"
            md_content += f"    <img src=\"https://img.shields.io/badge/Source_Code-View_on_GitHub-181717?style=for-the-badge&logo=github&logoColor=white\" />\n"
            md_content += "  </a>\n"
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
                    md_content +
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
