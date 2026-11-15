"""Sync Supabase and Backend environment variables to mobile/.env.local and mobile/.env.example."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# 1. Read root .env
vals: dict[str, str] = {}
env_file = ROOT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")

sub_url = vals.get("SUPABASE_URL", "")
anon_key = vals.get("SUPABASE_ANON_KEY", "")

# 2. Update mobile/.env.local
local_path = ROOT_DIR / "mobile" / ".env.local"
env_map: dict[str, str] = {}
if local_path.exists():
    for l in local_path.read_text(encoding="utf-8").splitlines():
        l = l.strip()
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1)
            env_map[k.strip()] = v.strip()

env_map.setdefault("EXPO_PUBLIC_API_URL", "http://localhost:8000")
env_map["EXPO_PUBLIC_SUPABASE_URL"] = sub_url
env_map["EXPO_PUBLIC_SUPABASE_ANON_KEY"] = anon_key

out = "# Auto-configured MediFlux Mobile Environment\n"
for k, v in sorted(env_map.items()):
    out += f"{k}={v}\n"
local_path.write_text(out, encoding="utf-8")

# 3. Create mobile/.env.example
example_path = ROOT_DIR / "mobile" / ".env.example"
example_path.write_text(
    "# MediFlux Mobile Environment Configuration Template\n"
    "EXPO_PUBLIC_API_URL=http://localhost:8000\n"
    "EXPO_PUBLIC_LAN_API_URL=http://192.168.1.100:8000\n"
    "EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co\n"
    "EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key\n",
    encoding="utf-8",
)

print(f"✓ Synchronized {local_path} and {example_path}")

