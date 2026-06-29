import os
import requests
import json
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
                print(f"Not found: {url}")
                return None
            if response.status_code == 403:
                print(f"Rate limited or forbidden: {url}")
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
             print("Warning: GEMINI_API_KEY not found. Analysis might be limited or fail.")
        self.gemini_client = genai.Client(api_key=api_key) if api_key else None

    def analyze_repo(self, repo: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
        repo_name = repo["name"]
        print(f"Analyzing {repo_name}...")

        # 1. Gather context
        topics = repo.get("topics", [])
        description = repo.get("description", "") or ""
        languages = list(self.github_client.get_repo_languages(repo_name).keys())

        context_files = []
        files_to_check = [
            "README.md", "pom.xml", "package.json", "build.gradle",
            "Dockerfile", "docker-compose.yml",
            "application.yml", "application.yaml", "application.properties",
            "src/main/resources/application.yml", "src/main/resources/application.yaml", "src/main/resources/application.properties"
        ]

        for filepath in files_to_check:
            content = self.github_client.get_file_content(repo_name, filepath)
            if content:
                # Truncate content to avoid exceeding context limits
                truncated_content = content[:2000]
                context_files.append(f"--- {filepath} ---\n{truncated_content}\n")

        context_str = "".join(context_files)

        if not self.gemini_client:
            print("Gemini API key missing, returning empty tech stack.")
            return []

        # 2. Call Gemini
        prompt = f"""
        Analyze the following repository to identify its key technologies and specific technical highlights.

        Repository Name: {repo_name}
        Description: {description}
        Topics: {', '.join(topics)}
        Languages: {', '.join(languages)}

        File Contents (truncated):
        {context_str}

        Based on this context, identify the 3 to 7 most important technologies used in this project.
        For each technology, provide:
        1. "name": The name of the technology (e.g., "Spring Boot", "React", "PostgreSQL").
        2. "color": A suitable shield.io hex color code WITHOUT the hash (e.g., "6DB33F").
        3. "logo": The exact name of the simpleicons logo for shields.io (e.g., "spring-boot").
        4. "highlight": A specific, highly technical sentence describing how this technology is used in the project based on the provided context (e.g., "Spring Boot 3.4.2 (Java 21) — REST API + WebSocket STOMP server"). DO NOT give generic descriptions like "Used for backend development."

        Return the result EXACTLY as a JSON array of objects, with no markdown formatting or backticks.
        Example format:
        [
            {{"name": "Java", "color": "ED8B00", "logo": "openjdk", "highlight": "Java 21 with sealed interfaces, records, pattern matching"}},
            {{"name": "Redis", "color": "DC382D", "logo": "redis", "highlight": "Redis-backed cart, refresh token blacklist, rate limiting"}}
        ]
        """

        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )

            # Parse JSON
            tech_stack_json = json.loads(response.text)

            tech_stack = []
            for item in tech_stack_json:
                tech_stack.append((
                    item.get("name", "Unknown"),
                    item.get("color", "000000"),
                    item.get("logo", "github"),
                    item.get("highlight", "Used in the project")
                ))
            return tech_stack

        except Exception as e:
            print(f"Error calling Gemini API: {e}")

        # Fallback to static analysis if Gemini fails or API key is missing
        print("Falling back to static analysis...")
        tech_stack_static = []
        added_techs = set()

        def add_tech(key: str) -> None:
            if key in TOPIC_TECH_MAP and key not in added_techs:
                tech_stack_static.append(TOPIC_TECH_MAP[key])
                added_techs.add(key)

        for topic in topics:
            add_tech(topic)

        for lang in languages:
            add_tech(lang.lower())

        return tech_stack_static


# Static mapping fallback
TOPIC_TECH_MAP = {
    "java": ("Java", "ED8B00", "openjdk", "Backend development using Java."),
    "spring-boot": ("Spring Boot", "6DB33F", "spring-boot", "Robust backend application using Spring Boot."),
    "spring-security": ("Spring Security", "6DB33F", "spring-security", "Secure authentication and authorization."),
    "microservices": ("Microservices", "E34F26", "spring", "Scalable distributed microservices architecture."),
    "kafka": ("Apache Kafka", "231F20", "apache-kafka", "Event-driven architecture and real-time messaging."),
    "redis": ("Redis", "DC382D", "redis", "High-performance caching and distributed sessions."),
    "docker": ("Docker", "2496ED", "docker", "Containerized deployment and environment consistency."),
    "kubernetes": ("Kubernetes", "326CE5", "kubernetes", "Automated container deployment and scaling."),
    "websocket": ("WebSocket", "010101", "socket.io", "Real-time bidirectional communication."),
    "jwt": ("JWT", "000000", "json-web-tokens", "Stateless authentication via JSON Web Tokens."),
    "mysql": ("MySQL", "4479A1", "mysql", "Relational database management."),
    "postgresql": ("PostgreSQL", "316192", "postgresql", "Advanced relational database management."),
    "mongodb": ("MongoDB", "4EA94B", "mongodb", "NoSQL document database."),
}


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
