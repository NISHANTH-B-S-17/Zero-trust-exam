import json
import os

def test_vercel_config_exists_and_valid():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    vercel_json_path = os.path.join(repo_root, "vercel.json")
    
    assert os.path.exists(vercel_json_path), "vercel.json must exist in root directory for Vercel deployment"
    
    with open(vercel_json_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    assert "version" in config or "builds" in config or "routes" in config or "rewrites" in config
    assert isinstance(config, dict)
