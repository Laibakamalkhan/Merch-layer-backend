import importlib
def load_plugin(import_path,*,policy):
    policy.assert_allowed()
    module_name,class_name=import_path.split(":",1)
    return getattr(importlib.import_module(module_name),class_name)
