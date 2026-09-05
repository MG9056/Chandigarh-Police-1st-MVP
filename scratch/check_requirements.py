import os
import ast
import re

backend_dir = r"c:\Users\shrih\Desktop\lmaoded\Chandigarh-Police-1st-MVP\backend"

std_lib = {
    "os", "sys", "json", "time", "datetime", "hashlib", "re", "math", "random",
    "typing", "contextlib", "io", "csv", "logging", "asyncio", "pathlib", "collections",
    "enum", "argparse", "functools", "copy", "traceback", "struct", "dataclasses", "abc"
}

imported_packages = set()

for root, dirs, files in os.walk(backend_dir):
    dirs[:] = [d for d in dirs if d not in ["__pycache__", "venv", ".venv", ".git"]]
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as file:
                try:
                    tree = ast.parse(file.read(), filename=f)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                pkg = alias.name.split(".")[0]
                                imported_packages.add(pkg)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                pkg = node.module.split(".")[0]
                                imported_packages.add(pkg)
                except Exception:
                    pass

# Filter out stdlib and internal backend modules
internal_modules = {
    "database", "models", "security", "rbac", "audit_service", "synthetic_data",
    "entity_resolution", "graph_adapter", "data", "pipelines", "routers", "crawler",
    "real_data"
}

external_imports = sorted(list(imported_packages - std_lib - internal_modules))
print("=== EXTERNAL PACKAGES IMPORTED ACROSS BACKEND ===")
for pkg in external_imports:
    print(f"  - {pkg}")

# Read requirements.txt
req_path = os.path.join(backend_dir, "requirements.txt")
with open(req_path, "r", encoding="utf-8") as f:
    req_lines = [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]

print("\n=== CURRENT REQUIREMENTS.TXT ENTRIES ===")
for r in req_lines:
    print(f"  - {r}")

# Map package import names to PyPI names
pypi_map = {
    "jwt": "PyJWT",
    "dotenv": "python-dotenv",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "sklearn": "scikit-learn"
}

missing_in_reqs = []
for pkg in external_imports:
    pypi_name = pypi_map.get(pkg, pkg).lower()
    # check if pypi_name or pkg is in any req line
    found = any(pypi_name in line or pkg.lower() in line for line in req_lines)
    if not found:
        missing_in_reqs.append(pypi_map.get(pkg, pkg))

print("\n=== PACKAGES IMPORTED BUT MISSING IN REQUIREMENTS.TXT ===")
for pkg in missing_in_reqs:
    print(f"  - {pkg}")
