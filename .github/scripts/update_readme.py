import os
import requests
import json
import re
import base64
from typing import Optional, List, Dict, Any, Tuple

# Mapping of topics to technical descriptions and badges
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

POM_TECH_MAPPINGS = {
    "spring-boot": "spring-boot",
    "spring-cloud": "microservices",
    "spring-kafka": "kafka",
    "kafka-clients": "kafka",
    "spring-data-redis": "redis",
    "jedis": "redis",
    "jjwt": "jwt",
    "java-jwt": "jwt",
    "mysql-connector": "mysql",
    "postgresql": "postgresql",
    "spring-data-mongodb": "mongodb",
    "spring-security": "spring-security",
    "spring-boot-starter-websocket": "websocket",
}

PACKAGE_JSON_TECH_MAPPINGS = {
    "jsonwebtoken": "jwt",
    "socket.io": "websocket",
    "ws": "websocket",
    "redis": "redis",
    "ioredis": "redis",
    "kafkajs": "kafka",
    "mysql": "mysql",
    "mysql2": "mysql",
    "pg": "postgresql",
    "mongodb": "mongodb",
    "mongoose": "mongodb",
}

GRADLE_TECH_MAPPINGS = {
    "spring-boot": "spring-boot",
    "spring-security": "spring-security",
}

CONFIG_TECH_MAPPINGS = {
    "mysql": "mysql",
    "postgresql": "postgresql",
    "mongodb": "mongodb",
    "redis": "redis",
    "kafka": "kafka",
}

class GitHubClient:
    def __init__(self, username: str, token: Optional[str] = None):
        self.username = username
        self.token = token
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def get(self, url: str) -> Optional[requests.Response]:
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
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

    def analyze_repo(self, repo: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
        repo_name = repo["name"]
        print(f"Analyzing {repo_name}...")
        topics = repo.get("topics", [])
        description = repo.get("description", "") or ""

        tech_stack: List[Tuple[str, str, str, str]] = []
        added_techs = set()

        def add_tech(key: str) -> None:
            if key in TOPIC_TECH_MAP and key not in added_techs:
                tech_stack.append(TOPIC_TECH_MAP[key])
                added_techs.add(key)

        # 1. Topics
        for topic in topics:
            add_tech(topic)

        # 2. Languages API
        languages = self.github_client.get_repo_languages(repo_name)
        for lang in languages:
            add_tech(lang.lower())

        # 3. Dependency files
        pom_xml = self.github_client.get_file_content(repo_name, "pom.xml")
        if pom_xml:
            add_tech("java")
            for keyword, tech in POM_TECH_MAPPINGS.items():
                if keyword in pom_xml:
                    add_tech(tech)

        package_json = self.github_client.get_file_content(repo_name, "package.json")
        if package_json:
            for keyword, tech in PACKAGE_JSON_TECH_MAPPINGS.items():
                if keyword in package_json:
                    add_tech(tech)

        build_gradle = self.github_client.get_file_content(repo_name, "build.gradle")
        if build_gradle:
            add_tech("java")
            for keyword, tech in GRADLE_TECH_MAPPINGS.items():
                if keyword in build_gradle:
                    add_tech(tech)

        dockerfile = self.github_client.get_file_content(repo_name, "Dockerfile")
        if dockerfile or self.github_client.get_file_content(repo_name, "docker-compose.yml"):
            add_tech("docker")

        if self.github_client.check_path_exists(repo_name, "k8s") or self.github_client.check_path_exists(repo_name, "kubernetes"):
            add_tech("kubernetes")

        # 4. Configuration files
        config_files = [
            "application.yml", "application.yaml", "application.properties",
            "src/main/resources/application.yml", "src/main/resources/application.yaml", "src/main/resources/application.properties"
        ]
        for config_file in config_files:
            content = self.github_client.get_file_content(repo_name, config_file)
            if content:
                for keyword, tech in CONFIG_TECH_MAPPINGS.items():
                    if keyword in content.lower():
                        add_tech(tech)

        # 5. Fallback scanning
        for key in TOPIC_TECH_MAP.keys():
            if key not in added_techs and re.search(r'\b' + re.escape(key.replace('-', ' ')) + r'\b', description, re.IGNORECASE):
                add_tech(key)
            elif key not in added_techs and key in ['kafka', 'redis', 'docker', 'kubernetes', 'websocket', 'jwt', 'mysql', 'postgresql', 'mongodb'] and re.search(r'\b' + re.escape(key) + r'\b', description, re.IGNORECASE):
                add_tech(key)

        # 6. Language fallback
        if not tech_stack and repo.get("language"):
            add_tech(repo["language"].lower())

        return tech_stack

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
