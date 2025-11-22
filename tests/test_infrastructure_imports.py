import importlib

modules_to_test = ["infrastructure", "infrastructure.voice", "infrastructure.model"]

for module in modules_to_test:
    try:
        imported_module = importlib.import_module(module)
        print(f"[PASS] Successfully imported module: {module}")
    except ModuleNotFoundError as e:
        print(f"[FAIL] Module not found: {module}. Error: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error while importing {module}: {e}")