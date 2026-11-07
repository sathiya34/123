import sqlite3
from pathlib import Path
import typer
from rich import print
from jinja2 import Template

DB_PATH = Path.home() / ".promptvault.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create prompts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            template TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create execution history log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_name TEXT,
            rendered_prompt TEXT,
            status TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_prompt(name: str, template_str: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO prompts (name, template) VALUES (?, ?)",
            (name, template_str)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        cursor.execute(
            "UPDATE prompts SET template = ?, version = version + 1 WHERE name = ?",
            (template_str, name)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def render_prompt(name: str, variables: dict) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT template FROM prompts WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise ValueError(f"Prompt '{name}' not found in local vault.")
    
    template = Template(row["template"])
    rendered = template.render(**variables)
    
    log_execution(name, rendered, "SUCCESS")
    return rendered

def log_execution(name: str, rendered: str, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO execution_logs (prompt_name, rendered_prompt, status) VALUES (?, ?, ?)",
        (name, rendered, status)
    )
    conn.commit()
    conn.close()

app = typer.Typer(help="PromptVault: Offline-first AI Prompt Management CLI")

@app.callback()
def main():
    init_db()

@app.command()
def add(name: str, template: str):
    """Save or update a prompt template in the local vault."""
    save_prompt(name, template)
    print(f"[green]✔ Prompt '{name}' successfully saved/updated in local SQLite vault![/green]")

@app.command()
def run(name: str, kwargs: list[str] = typer.Argument(None)):
    """Render a prompt template by passing key=value pairs."""
    var_dict = {}
    if kwargs:
        for kw in kwargs:
            if "=" in kw:
                k, v = kw.split("=", 1)
                var_dict[k] = v

    try:
        output = render_prompt(name, var_dict)
        print(f"\n[bold cyan]--- Rendered Prompt ({name}) ---[/bold cyan]")
        print(output)
        print("[bold cyan]------------------------------------[/bold cyan]\n")
    except Exception as e:
        print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    app()