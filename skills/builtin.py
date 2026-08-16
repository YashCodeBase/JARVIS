"""
A handful of starter skills so the loop is runnable end-to-end.
Replace the stubbed bits (weather API key, etc.) with your own API keys as
you go.
"""
import requests
import config
import datetime
import glob
import os
import shutil
import sqlite3
import subprocess

from ddgs import DDGS

from .base import Skill, registry

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "jarvis.db")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS briefing_log (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_date TEXT
        )"""
    )
    return conn


def has_briefed_today() -> bool:
    """Used by main.py to decide whether to auto-run the daily briefing on wake."""
    conn = _db()
    row = conn.execute("SELECT last_date FROM briefing_log WHERE id = 1").fetchone()
    conn.close()
    today = datetime.date.today().isoformat()
    return row is not None and row[0] == today


def mark_briefed_today() -> None:
    conn = _db()
    today = datetime.date.today().isoformat()
    conn.execute(
        "INSERT INTO briefing_log (id, last_date) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_date = excluded.last_date",
        (today,),
    )
    conn.commit()
    conn.close()


class GetTimeSkill(Skill):
    name = "get_time"
    description = "Get the current date and time."

    def execute(self, **kwargs) -> str:
        return datetime.datetime.now().strftime("It's %A, %B %d, %Y, %I:%M %p.")


class AddTaskSkill(Skill):
    name = "add_task"
    description = "Add a new task/to-do item to Jarvis's task list."
    parameters = {
        "type": "object",
        "properties": {"description": {"type": "string", "description": "What the task is"}},
        "required": ["description"],
    }

    def execute(self, description: str) -> str:
        conn = _db()
        conn.execute(
            "INSERT INTO tasks (description, created_at) VALUES (?, ?)",
            (description, datetime.datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        return f"Added task: {description}"


class ListOpenTasksSkill(Skill):
    name = "list_open_tasks"
    description = "List all tasks that are not yet marked done, e.g. 'what's left from yesterday'."

    def execute(self, **kwargs) -> str:
        conn = _db()
        rows = conn.execute(
            "SELECT id, description, created_at FROM tasks WHERE done = 0 ORDER BY created_at"
        ).fetchall()
        conn.close()
        if not rows:
            return "No open tasks. You're all caught up."
        lines = [f"#{r[0]}: {r[1]} (added {r[2][:10]})" for r in rows]
        return "Open tasks:\n" + "\n".join(lines)


class CompleteTaskSkill(Skill):
    name = "complete_task"
    description = "Mark a task as done by its id."
    parameters = {
        "type": "object",
        "properties": {"task_id": {"type": "integer"}},
        "required": ["task_id"],
    }

    def execute(self, task_id: int) -> str:
        conn = _db()
        conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
        return f"Marked task #{task_id} as done."


class OpenAppSkill(Skill):
    name = "open_app"
    description = (
        "Open an application or a URL on this computer, e.g. VS Code, a browser, "
        "Spotify, GIMP, or a website."
    )
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "App name (e.g. 'vscode', 'firefox', 'spotify') or a full URL",
            }
        },
        "required": ["target"],
    }

    # Quick-hit map for common apps where the launch command isn't just the
    # app's display name. Extend this freely as you find exceptions.
    APP_MAP = {
    "vscode": ["code"], "vs code": ["code"], "code": ["code"],
    "sublime": ["subl"], "sublime text": ["subl"],
    "chrome": ["google-chrome"], "google chrome": ["google-chrome"],
    "firefox": ["firefox"], "browser": ["xdg-open", "about:blank"],
    "files": ["nautilus"], "file manager": ["nautilus"],
    "terminal": ["gnome-terminal"],
    "settings": ["gnome-control-center"], "system settings": ["gnome-control-center"],
    "spotify": ["spotify"], "vlc": ["vlc"], "gimp": ["gimp"],
    "obs": ["obs"], "obs studio": ["obs"], "blender": ["blender"],
    "discord": ["discord"], "slack": ["slack"], "zoom": ["zoom"],
    "telegram": ["telegram-desktop"], "telegram desktop": ["telegram-desktop"],
    "whatsapp": ["whatsapp-for-linux"],
    "thunderbird": ["thunderbird"],
    "libreoffice": ["libreoffice"],
    "libreoffice writer": ["libreoffice", "--writer"],
    "libreoffice calc": ["libreoffice", "--calc"],
    "word": ["libreoffice", "--writer"], "excel": ["libreoffice", "--calc"],
    "steam": ["steam"],
    }

    def execute(self, target: str) -> str:
        target_clean = target.strip()
        target_lower = target_clean.lower()

        # 1. URL -> open in default browser
        if target_lower.startswith("http://") or target_lower.startswith("https://"):
            subprocess.Popen(["xdg-open", target_clean])
            return f"Opened {target_clean} in your default browser."

        # 2. Known quick-hit mapping
        if target_lower in self.APP_MAP:
            cmd = self.APP_MAP[target_lower]
            try:
                subprocess.Popen(cmd)
                return f"Launched {target_clean}."
            except FileNotFoundError:
                pass  # fall through to other strategies

        # 3. Target is directly a valid command on PATH (e.g. "firefox", "gimp", "vlc")
        exe = shutil.which(target_lower.replace(" ", "-")) or shutil.which(target_lower)
        if exe:
            subprocess.Popen([exe])
            return f"Launched {target_clean}."

        # 4. Search installed .desktop entries for a fuzzy name match, then
        #    launch via gtk-launch (standard on GNOME/most Linux desktops).
        match = self._find_desktop_entry(target_lower)
        if match:
            try:
                subprocess.Popen(["gtk-launch", match])
                return f"Launched {target_clean}."
            except FileNotFoundError:
                return (
                    f"Found '{target_clean}' as {match}, but 'gtk-launch' isn't available. "
                    f"Install it with: sudo apt install libgtk2.0-bin"
                )

        return (
            f"Couldn't find an app matching '{target_clean}'. Add it to APP_MAP in "
            f"skills/builtin.py if you know the exact launch command."
        )

    @staticmethod
    def _find_desktop_entry(query: str) -> str | None:
        """Search standard Linux app directories for a .desktop file whose
        Name matches the query, return its desktop-id (filename) for gtk-launch."""
        search_dirs = [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications"),
        ]

        candidates = []
        for d in search_dirs:
            candidates.extend(glob.glob(os.path.join(d, "*.desktop")))

        best_match = None
        for path in candidates:
            desktop_id = os.path.basename(path)
            name = None
            try:
                with open(path, "r", errors="ignore") as f:
                    for line in f:
                        if line.startswith("Name=") and name is None:
                            name = line.strip().split("=", 1)[1]
                            break
            except OSError:
                continue

            if not name:
                continue

            name_lower = name.lower()
            # Exact or substring match on the app's display name
            if query == name_lower:
                return desktop_id  # exact match wins immediately
            if query in name_lower or name_lower in query:
                best_match = best_match or desktop_id

        return best_match


class WebSearchSkill(Skill):
    name = "web_search"
    description = (
        "Search the web for current information — news, facts, recommendations, "
        "reviews, 'what's happening in the world', game/product suggestions, etc. "
        "Use this whenever a request needs up-to-date or specific information you "
        "don't already know."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for"},
            "max_results": {
                "type": "integer",
                "description": "How many results to return (default 5)",
            },
        },
        "required": ["query"],
    }

    def execute(self, query: str, max_results: int = 5) -> str:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            return f"Web search failed: {e}"

        if not results:
            return f"No results found for '{query}'."

        lines = []
        for r in results:
            title = r.get("title", "").strip()
            body = r.get("body", "").strip()
            url = r.get("href", "").strip()
            lines.append(f"- {title}: {body} ({url})")
        return f"Search results for '{query}':\n" + "\n".join(lines)


class DailyBriefingSkill(Skill):
    name = "daily_briefing"
    description = (
        "Give a full daily briefing: a greeting, today's top news headlines, and "
        "the user's open/incomplete tasks. Use this for 'good morning', 'give me "
        "my briefing', 'what's going on today', or similar broad wake-up requests — "
        "not for narrow single-topic questions (use news_briefing or web_search "
        "for those instead)."
    )

    def execute(self, **kwargs) -> str:
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning."
        elif hour < 17:
            greeting = "Good afternoon."
        else:
            greeting = "Good evening."

        news = NewsBriefingSkill().execute()
        tasks = ListOpenTasksSkill().execute()

        return (
            f"{greeting} Here's your briefing.\n\n"
            f"{news}\n\n"
            f"{tasks}\n\n"
            f"What would you like to work on?"
        )


class NewsBriefingSkill(Skill):
    name = "news_briefing"
    description = (
        "Get a short briefing of recent news headlines, e.g. for 'what's happening "
        "in the world today' or a morning briefing. Optionally scoped to a topic."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Optional topic to focus on (e.g. 'technology', 'India'). "
                "Leave blank for general top headlines.",
            },
        },
        "required": [],
    }

    def execute(self, topic: str = "") -> str:
        query = topic.strip() if topic else "world news today"
        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=6))
        except Exception as e:
            return f"News search failed: {e}"

        if not results:
            return "Couldn't find any news right now."

        lines = []
        for r in results:
            title = r.get("title", "").strip()
            source = r.get("source", "").strip()
            date = r.get("date", "").strip()[:10]
            lines.append(f"- {title} ({source}, {date})")
        return "Today's headlines:\n" + "\n".join(lines)




class ShowMapSkill(Skill):
    name = "show_map"
    description = (
        "Show an interactive map with markers for one or more place names — "
        "cities, countries, regions, landmarks. Use this whenever the user asks "
        "to see something 'on a map', or after search/news results mention "
        "specific locations worth visualizing, e.g. multiple cities/regions "
        "involved in a news story or conflict."
    )
    parameters = {
        "type": "object",
        "properties": {
            "places": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Place names to plot, e.g. ['Kyiv', 'Moscow', 'Donetsk']",
            },
            "title": {"type": "string", "description": "Optional map title"},
        },
        "required": ["places"],
    }

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    HEADERS = {"User-Agent": "JarvisPersonalAssistant/1.0 (personal use)"}

    def execute(self, places: list, title: str = "Map") -> str:
        markers = []
        for place in places:
            try:
                resp = requests.get(
                    self.NOMINATIM_URL,
                    params={"q": place, "format": "json", "limit": 1},
                    headers=self.HEADERS,
                    timeout=8,
                )
                results = resp.json()
                if results:
                    lat = float(results[0]["lat"])
                    lon = float(results[0]["lon"])
                    markers.append((place, lat, lon))
            except Exception:
                pass
            time.sleep(1)  # respect Nominatim's 1 request/second rate limit

        if not markers:
            return f"Couldn't find coordinates for any of: {', '.join(places)}"

        html = self._build_html(markers, title)
        out_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "jarvis_map.html")
        )
        with open(out_path, "w") as f:
            f.write(html)

        try:
            subprocess.Popen(["xdg-open", out_path])
        except Exception as e:
            return f"Map saved to {out_path} but couldn't auto-open it: {e}"

        found_names = ", ".join(m[0] for m in markers)
        missing = set(places) - {m[0] for m in markers}
        result = f"Opened a map showing: {found_names}."
        if missing:
            result += f" (Couldn't find: {', '.join(missing)})"
        return result

    @staticmethod
    def _build_html(markers, title) -> str:
        avg_lat = sum(m[1] for m in markers) / len(markers)
        avg_lon = sum(m[2] for m in markers) / len(markers)
        zoom = 4 if len(markers) > 1 else 8
        markers_js = "\n".join(
            f'    L.marker([{lat}, {lon}]).addTo(map).bindPopup({name!r});'
            for name, lat, lon in markers
        )
        return f"""<!DOCTYPE html>
<html>
<head>
  <title>{title}</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style> html, body, #map {{ height: 100%; margin: 0; }} </style>
</head>
<body>
  <div id="map"></div>
  <script>
    var map = L.map('map').setView([{avg_lat}, {avg_lon}], {zoom});
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);
{markers_js}
  </script>
</body>
</html>"""





class WeatherSkill(Skill):
    name = "get_weather"
    description = "Get the current weather for a city."
    parameters = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }

    def execute(self, city: str) -> str:
        api_key = getattr(config, "WEATHER_API_KEY", "")
        if not api_key:
            return (
                "Weather isn't set up yet — add a free OpenWeatherMap key "
                "(https://openweathermap.org/api) to WEATHER_API_KEY in config.py."
            )

        try:
            resp = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": api_key, "units": "metric"},
                timeout=8,
            )
        except requests.RequestException as e:
            return f"Couldn't reach the weather service: {e}"

        if resp.status_code == 401:
            return (
                "Weather API key was rejected (401). If you just created it, "
                "OpenWeatherMap keys can take up to ~2 hours to activate — try again shortly."
            )
        if resp.status_code == 404:
            return f"Couldn't find a city called '{city}'. Check the spelling?"
        if resp.status_code != 200:
            return f"Weather service returned an error ({resp.status_code})."

        data = resp.json()
        try:
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            condition = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            wind = data["wind"]["speed"]
        except (KeyError, IndexError):
            return "Got a response but couldn't parse the weather data."

        return (
            f"{city.title()}: {condition}, {temp:.0f}°C (feels like {feels_like:.0f}°C), "
            f"{humidity}% humidity, wind {wind} m/s."
        )

def register_builtin_skills() -> None:
    for skill_cls in (
        GetTimeSkill,
        AddTaskSkill,
        ListOpenTasksSkill,
        CompleteTaskSkill,
        OpenAppSkill,
        WebSearchSkill,
        NewsBriefingSkill,
        DailyBriefingSkill,
        ShowMapSkill,
        WeatherSkill,
    ):
        registry.register(skill_cls())
